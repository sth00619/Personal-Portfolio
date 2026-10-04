"""Tests for leakage, chronology, scoring, and PSI alarm behavior."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data import FEATURES, assert_feature_allowlist, expanding_month_splits
from src.experiment import write_scorecard_points
from src.metrics import PSI_RETRAIN, auc_gini, population_stability_index, psi_signal
from src.models import BASE_GOOD_BAD_ODDS, BASE_SCORE, POINTS_TO_DOUBLE_ODDS, fit_scorecard, pd_to_points

ROWS_PER_MONTH = 120
MONTH_COUNT = 6
SYNTHETIC_ROWS = 600
RANDOM_STATE = 7


@pytest.mark.parametrize("forbidden", ["Default", "issue_d", "loan_status", "recoveries", "grade"])
def test_feature_allowlist_rejects_leakage_fields(forbidden: str) -> None:
    """Outcome, time, post-decision, and derived decision fields must fail closed."""
    with pytest.raises(ValueError):
        assert_feature_allowlist([*FEATURES, forbidden])


def test_expanding_split_never_trains_on_validation_month() -> None:
    """Every validation month must follow all training observations."""
    months = pd.period_range("2016-01", periods=MONTH_COUNT, freq="M").astype(str)
    frame = pd.DataFrame({"month": np.repeat(months, ROWS_PER_MONTH)})
    folds = expanding_month_splits(frame, validation_months=2, min_train_months=3)
    assert len(folds) == 2
    for month, train, validation in folds:
        assert train["month"].max() < month
        assert validation["month"].unique().tolist() == [month]


def test_psi_detects_shift_and_sets_retrain_signal() -> None:
    """A severe population shift must cross the retraining review threshold."""
    reference = np.linspace(0.01, 0.99, 1000)
    shifted = np.linspace(0.70, 0.99, 1000)
    assert population_stability_index(reference, reference) == pytest.approx(0.0)
    psi = population_stability_index(reference, shifted)
    assert psi > PSI_RETRAIN
    assert psi_signal(psi) == "RETRAIN_REVIEW"
    assert psi_signal(0.15) == "INVESTIGATE"


def test_pdo_adds_fifty_points_when_good_odds_double() -> None:
    """Score scale must add 50 points for a twofold increase in good/bad odds."""
    first = pd_to_points(np.array([0.20]))[0]
    second = pd_to_points(np.array([1 / 9]))[0]
    assert second - first == pytest.approx(50.0)
    assert pd_to_points(np.array([1 / 21]))[0] == pytest.approx(600.0)


def test_woe_model_handles_out_of_time_values_without_refit(tmp_path: Path) -> None:
    """Training-only bins should score later values and yield valid discrimination."""
    rng = np.random.default_rng(RANDOM_STATE)
    frame = pd.DataFrame(
        {
            "revenue": rng.normal(65000, 15000, SYNTHETIC_ROWS),
            "dti_n": rng.uniform(1, 35, SYNTHETIC_ROWS),
            "loan_amnt": rng.uniform(2000, 30000, SYNTHETIC_ROWS),
            "fico_n": rng.uniform(600, 800, SYNTHETIC_ROWS),
            "experience_c": rng.integers(0, 2, SYNTHETIC_ROWS),
        }
    )
    risk = 0.1 + 0.01 * frame["dti_n"] - 0.002 * (frame["fico_n"] - 600)
    target = rng.binomial(1, np.clip(risk, 0.05, 0.7)).astype(int)
    model = fit_scorecard(frame.iloc[:500], target[:500])
    predictions = model.predict_pd(frame.iloc[500:])
    assert len(predictions) == 100
    assert np.all((predictions > 0) & (predictions < 1))
    assert np.isfinite(predictions).all()
    assert auc_gini(target[500:], predictions)[0] >= 0.4
    factor = POINTS_TO_DOUBLE_ODDS / np.log(2)
    intercept_points = BASE_SCORE - factor * np.log(BASE_GOOD_BAD_ODDS) - factor * model.model.intercept_[0]
    bin_points = -factor * model.transform(frame.iloc[500:]) * model.model.coef_[0]
    assert np.allclose(model.score(frame.iloc[500:]), intercept_points + bin_points.sum(axis=1))
    write_scorecard_points(model, tmp_path)
    assert not pd.read_csv(tmp_path / "scorecard_bins.csv").empty
    scaling = json.loads((tmp_path / "scorecard_scaling.json").read_text())
    assert scaling["intercept_points"] == pytest.approx(intercept_points)
