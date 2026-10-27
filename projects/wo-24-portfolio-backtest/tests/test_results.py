"""Regression checks for the committed Ship Gate outputs."""

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_monthly_ten_basis_point_comparison_matches_reported_result() -> None:
    """The report's headline returns and risk metrics match the committed CSV."""
    summary = pd.read_csv(PROJECT_ROOT / "results" / "scenario_summary.csv")
    current = summary.query("universe == 'current_only' and rebalance == 'monthly' and cost_bps_per_traded_value == 10").iloc[0]
    extended = summary.query("universe == 'delisted_included' and rebalance == 'monthly' and cost_bps_per_traded_value == 10").iloc[0]
    assert current["total_return"] == pytest.approx(0.649012, abs=1e-5)
    assert extended["total_return"] == pytest.approx(-0.085349, abs=1e-5)
    assert current["sharpe"] == pytest.approx(0.487811, abs=1e-5)
    assert extended["sharpe"] == pytest.approx(0.093497, abs=1e-5)
    assert extended["max_drawdown"] < current["max_drawdown"]


def test_cost_sensitivity_and_delisted_price_coverage_are_visible() -> None:
    """Higher assumed costs reduce expanded-universe returns, with missing prices counted."""
    summary = pd.read_csv(PROJECT_ROOT / "results" / "scenario_summary.csv")
    extended = summary.query("universe == 'delisted_included' and rebalance == 'monthly'").sort_values("cost_bps_per_traded_value")
    assert extended["total_return"].is_monotonic_decreasing

    coverage = pd.read_csv(PROJECT_ROOT / "results" / "universe_coverage.csv").set_index("Universe")
    assert coverage.loc["delisted", "price_histories"] == 139
    assert coverage.loc["delisted", "missing_price_histories"] == 0
    assert coverage.loc["current", "missing_price_histories"] == 2
