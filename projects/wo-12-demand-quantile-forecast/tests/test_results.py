"""Regression checks for the committed WO-12 Ship Gate evidence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_DIR / "results"
EXPECTED_ITEMS = 1_437
HORIZON = 28
FOLDS = 3
NOMINAL_COVERAGE = 0.8


def load_metrics() -> pd.DataFrame:
    """Load the committed Ship Gate evidence table."""

    return pd.read_csv(RESULTS_DIR / "ship_gate_metrics.csv")


def select_row(metrics: pd.DataFrame, scope: str, segment: str, model: str) -> pd.Series:
    """Select exactly one metric row for an evaluation slice."""

    rows = metrics.loc[
        (metrics["scope"] == scope)
        & (metrics["segment"] == segment)
        & (metrics["model"] == model)
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def test_ship_gate_has_expected_evaluation_denominator() -> None:
    """The item result must include every item, horizon step, and fold."""

    row = select_row(load_metrics(), "item", "all", "quantile")
    assert int(row["observations"]) == EXPECTED_ITEMS * HORIZON * FOLDS
    assert int(row["covered"]) <= int(row["observations"])
    assert np.isclose(row["coverage"], row["covered"] / row["observations"])


def test_quantile_models_improve_distributional_loss() -> None:
    """The measured quantile system must beat the degenerate point distribution."""

    metrics = load_metrics()
    baseline = select_row(metrics, "item", "all", "point_baseline")
    quantile = select_row(metrics, "item", "all", "quantile")
    assert quantile["mean_pinball_loss"] < baseline["mean_pinball_loss"]


def test_segment_and_hierarchy_evidence_is_present() -> None:
    """Both demand segments and both hierarchy levels must retain measurements."""

    metrics = load_metrics()
    for segment in ("intermittent", "regular"):
        row = select_row(metrics, "item", segment, "quantile")
        assert 0.0 <= row["coverage"] <= 1.0
    aggregate = select_row(metrics, "aggregate", "all", "quantile")
    assert 0.0 <= aggregate["coverage"] <= 1.0
    assert not np.isclose(aggregate["coverage"], NOMINAL_COVERAGE)

