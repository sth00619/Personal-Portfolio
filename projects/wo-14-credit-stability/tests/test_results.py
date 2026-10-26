"""Regression tests for committed WO-14 evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_DIR / "results"


def test_ship_gate_tables_are_complete() -> None:
    """Committed evidence must contain all declared model and PSI comparisons."""

    metrics = pd.read_csv(RESULTS_DIR / "model_metrics.csv")
    assert metrics["variant"].tolist() == [
        "baseline_application",
        "extended_include_high_missing",
        "extended_exclude_high_missing",
    ]
    assert metrics["comparison_rows"].eq(61_503).all()
    assert metrics["roc_auc"].between(0.5, 1.0).all()
    assert metrics.loc[1, "roc_auc"] > metrics.loc[0, "roc_auc"]

    top = pd.read_csv(RESULTS_DIR / "top_10_psi.csv")
    assert top.groupby("variant").size().eq(10).all()
    assert top["rank"].between(1, 10).all()

    high_missing = pd.read_csv(RESULTS_DIR / "high_missing_aggregate_features.csv")
    assert len(high_missing) == 6
    assert high_missing["reference_missing_rate"].ge(0.5).all()


def test_summary_preserves_proxy_split_boundary() -> None:
    """The evidence file must never present the ID proxy as real temporal validation."""

    summary = json.loads((RESULTS_DIR / "tradeoff_summary.json").read_text())
    assert summary["split"]["is_true_temporal_validation"] is False
    assert summary["split"]["reference_rows"] == 246_008
    assert summary["split"]["comparison_rows"] == 61_503


def test_result_figures_are_nonempty() -> None:
    """Every portfolio figure must exist and contain rendered output."""

    for name in ("auc_psi_tradeoff.png", "missing_ablation.png", "top_10_psi.png"):
        assert (RESULTS_DIR / name).stat().st_size > 10_000

