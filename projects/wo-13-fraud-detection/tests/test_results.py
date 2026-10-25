"""Regression checks for committed WO-13 Ship Gate evidence."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_DIR / "results"
EXPECTED_ROWS = 590_540
EXPECTED_FRAUD = 20_663
EXPECTED_HOLDOUT = 118_108


def load_summary() -> dict[str, object]:
    """Load the committed structured experiment summary."""

    return json.loads((RESULTS_DIR / "summary.json").read_text(encoding="utf-8"))


def test_dataset_denominators_match_verified_source() -> None:
    """The experiment must retain all verified transactions and fraud labels."""

    summary = load_summary()
    dataset = summary["dataset"]
    assert dataset["rows"] == EXPECTED_ROWS
    assert dataset["fraud_count"] == EXPECTED_FRAUD
    assert dataset["time_test_rows"] == EXPECTED_HOLDOUT


def test_random_split_reports_observed_optimism() -> None:
    """Committed random-split PR-AUC must exceed chronological holdout PR-AUC."""

    ship_gate = load_summary()["ship_gate"]
    assert ship_gate["random_pr_auc"] > ship_gate["temporal_pr_auc"]
    assert np.isclose(
        ship_gate["random_minus_temporal_pr_auc_pp"],
        (ship_gate["random_pr_auc"] - ship_gate["temporal_pr_auc"]) * 100,
    )


def test_validation_selected_threshold_reduces_test_cost() -> None:
    """The untouched holdout must show the selected threshold's realized cost."""

    ship_gate = load_summary()["ship_gate"]
    sweep = pd.read_csv(RESULTS_DIR / "threshold_sweep.csv")
    assert sweep["selected_on_validation"].sum() == 1
    assert sweep["default_threshold"].sum() == 1
    assert ship_gate["selected_threshold_cost"] < ship_gate["default_threshold_cost"]


def test_missing_feature_ablation_has_both_policies() -> None:
    """The result table must preserve include and drop comparisons."""

    metrics = pd.read_csv(RESULTS_DIR / "ranking_metrics.csv")
    ablation = metrics.loc[metrics["experiment"] == "missing_ablation"]
    assert set(ablation["feature_policy"]) == {
        "include_all",
        "drop_gt_90pct_missing",
    }
    assert set(ablation["metric"]) == {"pr_auc", "roc_auc"}
