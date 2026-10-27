"""Regression checks for the portfolio mechanics and Ship Gate metrics."""

import numpy as np
import pandas as pd
import pytest

from wo24.backtest import compound_fixed_shares, run_backtest, select_momentum_weights, summarize_returns


def test_momentum_selection_uses_only_prices_through_rebalance_close() -> None:
    """Future prices cannot change a previously calculated momentum ranking."""
    dates = pd.date_range("2020-01-01", periods=8, freq="B")
    prices = pd.DataFrame(
        {"winner": [100, 102, 104, 106, 108, 110, 500, 500], "loser": [100, 99, 98, 97, 96, 95, 1, 1]},
        index=dates,
    )
    first = select_momentum_weights(prices, dates[5], prices.columns, portfolio_size=1, lookback_sessions=2)
    altered_future = prices.copy()
    altered_future.loc[dates[6]:, "winner"] = 1
    altered = select_momentum_weights(altered_future, dates[5], prices.columns, portfolio_size=1, lookback_sessions=2)
    assert first.to_dict() == altered.to_dict() == {"winner": 1.0}


def test_momentum_ties_have_stable_symbol_order() -> None:
    """Equal momentum scores select the same ticker regardless of input iteration order."""
    dates = pd.date_range("2020-01-01", periods=6, freq="B")
    prices = pd.DataFrame({"b": [100, 101, 102, 103, 104, 105], "a": [100, 101, 102, 103, 104, 105]}, index=dates)
    first = select_momentum_weights(prices, dates[5], ["b", "a"], portfolio_size=1, lookback_sessions=2)
    second = select_momentum_weights(prices, dates[5], ["a", "b"], portfolio_size=1, lookback_sessions=2)
    assert first.to_dict() == second.to_dict() == {"a": 1.0}


def test_positive_transaction_cost_reduces_net_return() -> None:
    """Turnover fees lower the portfolio result when a trade occurs."""
    dates = pd.bdate_range("2018-01-01", periods=330)
    rising = np.linspace(100.0, 180.0, len(dates))
    falling = np.linspace(100.0, 90.0, len(dates))
    prices = pd.DataFrame({"a": rising, "b": falling}, index=dates)
    free, _ = run_backtest(prices, prices.columns, cost_bps=0, portfolio_size=1, start="2018-01-01")
    charged, turnover = run_backtest(prices, prices.columns, cost_bps=100, portfolio_size=1, start="2018-01-01")
    assert turnover.sum() > 0
    assert (1 + charged).prod() < (1 + free).prod()


def test_holdings_drift_without_daily_rebalancing() -> None:
    """A monthly holding period compounds fixed shares instead of restoring target weights daily."""
    dates = pd.date_range("2024-01-02", periods=2, freq="B")
    asset_returns = pd.DataFrame({"a": [0.10, 0.10], "b": [0.0, 0.0]}, index=dates)
    returns, ending_weights = compound_fixed_shares(
        asset_returns,
        pd.Series({"a": 0.5, "b": 0.5}),
        cost_bps=0,
        traded_notional=0,
    )
    assert returns.iloc[0] == pytest.approx(0.05)
    assert returns.iloc[1] == pytest.approx(0.05238095)
    assert ending_weights["a"] > 0.5


def test_summary_metrics_have_expected_signs() -> None:
    """A known losing path produces a negative return and drawdown."""
    metrics = summarize_returns(pd.Series([-0.01, -0.02, 0.01]))
    assert metrics["total_return"] < 0
    assert metrics["max_drawdown"] < 0
    assert np.isfinite(metrics["sharpe"])
