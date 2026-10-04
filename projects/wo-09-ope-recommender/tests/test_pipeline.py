"""Behavioral checks for logged-support OPE and two-stage recommendation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiment import (
    FeatureStore, candidate_scores, epsilon_slate_policy,
    logged_ranking_metrics, reconstruct_bts_policy, rerank, top_candidates,
)
from src.ope import ESTIMATOR_NAMES, estimate_policy


def test_position_standardized_ope_matches_obp_and_bootstraps() -> None:
    """Known uniform policy returns factual reward for each OPE estimator."""
    n = 60
    actions = np.tile(np.array([0, 1]), n // 2)
    positions = np.tile(np.array([0, 1, 2]), n // 3)
    rewards = np.tile(np.array([0, 1, 0, 0, 1, 0]), n // 6)
    feedback = {
        "n_rounds": n, "n_actions": 2,
        "action": actions, "position": positions,
        "reward": rewards, "pscore": np.full(n, 0.5),
        "context": np.zeros((n, 1)), "action_context": np.eye(2),
    }
    policy = np.full((n, 2, 3), 0.5)
    q_hat = np.full((n, 2, 3), 1 / 3)
    result = estimate_policy(feedback, policy, q_hat, n_bootstrap=50)
    for name in ESTIMATOR_NAMES:
        assert result["estimates"][name] == pytest.approx(1 / 3)
        assert result["intervals"][name][0] <= result["intervals"][name][1]
    assert result["diagnostics"]["effective_sample_size"] == pytest.approx(n)


def test_ope_rejects_missing_support_or_invalid_policy() -> None:
    """Zero logging propensity and malformed action probabilities fail early."""
    feedback = {
        "action": np.array([0, 1, 0]),
        "position": np.array([0, 1, 2]),
        "reward": np.array([1, 0, 1]),
        "pscore": np.array([0.5, 0.0, 0.5]),
    }
    distribution = np.full((3, 2, 3), 0.5)
    q_hat = np.full_like(distribution, 0.1)
    with pytest.raises(ValueError, match="Positive propensities"):
        estimate_policy(feedback, distribution, q_hat, n_bootstrap=5)
    feedback["pscore"][1] = 0.5
    distribution[0, :, 0] = 0.25
    with pytest.raises(ValueError, match="normalized"):
        estimate_policy(feedback, distribution, q_hat, n_bootstrap=5)


def test_two_stage_policy_has_support_and_unique_ranked_items() -> None:
    """Retrieved candidates rerank without duplicates and preserve overlap."""
    n_actions = 12
    store = FeatureStore(
        user_codes=np.zeros((8, 4), dtype=np.int32),
        affinity=np.zeros((8, n_actions), dtype=np.float32),
        item_numeric=np.zeros(n_actions),
        item_categories=np.zeros((n_actions, 3), dtype=np.int32),
    )
    store.affinity[7, 5] = 3.0
    actions = np.array([0, 1, 2, 3, 4, 5])
    rewards = np.array([1, 0, 0, 1, 0, 0])
    hybrid, popularity, diagnostics = candidate_scores(store, actions, rewards, 6)
    candidates, baseline = top_candidates(hybrid, popularity)
    assert candidates.shape == (2, 10)
    assert baseline.shape == (2, 10)
    assert diagnostics["cf_context_coverage"] == pytest.approx(0.5)
    q_hat = np.tile(np.linspace(0.01, 0.1, n_actions)[None, :, None], (2, 1, 3))
    ranked = rerank(candidates, q_hat)
    assert all(len(set(row)) == 3 for row in ranked)
    distribution = epsilon_slate_policy(ranked, n_actions)
    assert np.all(distribution > 0)
    assert np.allclose(distribution.sum(axis=1), 1.0)


def test_logged_ranking_metrics_condition_on_observed_click() -> None:
    """A clicked item at rank one gives full nDCG for its position."""
    actions = np.array([2, 2, 2])
    positions = np.array([0, 1, 2])
    rewards = np.ones(3, dtype=int)
    candidates = np.tile(np.arange(10), (3, 1))
    ranked = np.tile(np.array([2, 1, 3]), (3, 1))
    metrics = logged_ranking_metrics(actions, positions, rewards, candidates, ranked)
    assert metrics["recall_at_10"] == pytest.approx(1.0)
    assert metrics["ndcg_at_3"] == pytest.approx(1.0)


def test_bts_reconstruction_reserves_independent_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Action-only fit and held-out click measurement use disjoint target rows."""
    import src.experiment as experiment

    target = tmp_path / "bts" / "men"
    target.mkdir(parents=True)
    n = 600
    frame = pd.DataFrame({
        "timestamp": ["2019-11-28 16:00:00+00:00"] * n,
        "item_id": [0 if index % 5 else 1 for index in range(n)],
        "position": [index % 3 + 1 for index in range(n)],
        "click": [int(index % 17 == 0) for index in range(n)],
    })
    frame.to_csv(target / "men.csv", index=False)
    monkeypatch.setattr(experiment, "RAW", tmp_path)
    dist, observed, diagnostics = reconstruct_bts_policy(
        "2019-11-28 15:00:00+00:00",
        pd.Series(["2019-11-28 16:00:00+00:00"] * 3),
        2, np.full((2, 3), 0.5),
    )
    assert dist.shape == (3, 2, 3)
    assert np.allclose(dist.sum(axis=1), 1)
    assert diagnostics["policy_fit_rows"] + diagnostics["truth_rows"] == n
    assert observed["rows"] == diagnostics["truth_rows"]
    assert diagnostics["fit_vs_holdout_weighted_tv"] < diagnostics["fixed_prior_vs_holdout_weighted_tv"]


def test_saved_ship_gate_artifacts() -> None:
    """Measured tables retain four estimators and agree with the JSON report."""
    root = Path(__file__).resolve().parents[1]
    report_path = root / "results" / "report.json"
    if not report_path.exists():
        pytest.skip("Run the experiment to create measured outputs")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    benchmark = pd.read_csv(root / "results" / "ope_benchmark.csv")
    ranking = pd.read_csv(root / "results" / "ranking_metrics.csv")
    assert set(benchmark.estimator) == {"DM", "IPS", "SNIPS", "DR"}
    assert len(ranking) == 2
    assert benchmark.observed_bts.nunique() == 1
    assert benchmark.observed_bts.iloc[0] == pytest.approx(
        report["observed_bts"]["standardized_rate"]
    )
    assert benchmark.ci_lower.le(benchmark.ci_upper).all()
    assert (root / "results" / "ope_benchmark.png").exists()
    assert (root / "results" / "ranking_metrics.png").exists()
