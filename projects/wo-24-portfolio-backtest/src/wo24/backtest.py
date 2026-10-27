"""A no-look-ahead monthly momentum backtest with explicit trading costs."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from wo24.config import (
    BACKTEST_END,
    BACKTEST_START,
    BASIS_POINTS_PER_RATIO,
    LOOKBACK_SESSIONS,
    PORTFOLIO_SIZE,
)


def build_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Convert observed prices to returns; post-delisting stale marks become zero returns."""
    filled = prices.ffill()
    returns = filled.pct_change(fill_method=None)
    returns = returns.mask(prices.isna() & prices.shift(1).notna(), 0.0)
    return returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def select_momentum_weights(
    prices: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    eligible_symbols: Iterable[str],
    portfolio_size: int = PORTFOLIO_SIZE,
    lookback_sessions: int = LOOKBACK_SESSIONS,
) -> pd.Series:
    """Select equal-weight leaders using only prices available at rebalance close."""
    dates = prices.index[prices.index <= rebalance_date]
    if len(dates) <= lookback_sessions:
        return pd.Series(dtype="float64")
    current_date = dates[-1]
    prior_date = dates[-(lookback_sessions + 1)]
    candidates = sorted({symbol for symbol in eligible_symbols if symbol in prices.columns})
    momentum = prices.loc[current_date, candidates] / prices.loc[prior_date, candidates] - 1.0
    momentum = momentum.replace([np.inf, -np.inf], np.nan).dropna().sort_values(
        ascending=False,
        kind="mergesort",
    )
    selected = momentum.head(portfolio_size).index
    if len(selected) == 0:
        return pd.Series(dtype="float64")
    return pd.Series(1.0 / len(selected), index=selected, dtype="float64")


def _rebalance_dates(index: pd.DatetimeIndex, frequency: str) -> list[pd.Timestamp]:
    """Return the last available trading session for each requested period."""
    month_ends = pd.Series(index, index=index).groupby(index.to_period("M")).last().tolist()
    if frequency == "monthly":
        return month_ends
    if frequency == "quarterly":
        return [date for position, date in enumerate(month_ends) if (position + 1) % 3 == 0]
    raise ValueError(f"Unsupported rebalance frequency: {frequency}")


def compound_fixed_shares(
    asset_returns: pd.DataFrame,
    initial_weights: pd.Series,
    cost_bps: float,
    traded_notional: float,
) -> tuple[pd.Series, pd.Series]:
    """Compound a buy-and-hold basket between rebalances and return ending weights."""
    holdings = initial_weights.reindex(asset_returns.columns, fill_value=0.0).astype("float64")
    portfolio_returns = pd.Series(0.0, index=asset_returns.index, name="return")
    if holdings.sum() <= 0:
        if len(portfolio_returns):
            portfolio_returns.iloc[0] = -(cost_bps / BASIS_POINTS_PER_RATIO) * traded_notional
        return portfolio_returns, holdings
    fee_multiplier = 1.0 - (cost_bps / BASIS_POINTS_PER_RATIO) * traded_notional
    for position, (date, daily_asset_returns) in enumerate(asset_returns.iterrows()):
        gross_return = float(holdings.dot(daily_asset_returns))
        if position == 0:
            portfolio_returns.loc[date] = (1.0 + gross_return) * fee_multiplier - 1.0
        else:
            portfolio_returns.loc[date] = gross_return
        gross_growth = 1.0 + gross_return
        if gross_growth > 0:
            holdings = holdings.mul(1.0 + daily_asset_returns).div(gross_growth)
    return portfolio_returns, holdings


def run_backtest(
    prices: pd.DataFrame,
    symbols: Iterable[str],
    cost_bps: float = 0.0,
    frequency: str = "monthly",
    portfolio_size: int = PORTFOLIO_SIZE,
    lookback_sessions: int = LOOKBACK_SESSIONS,
    start: str = BACKTEST_START,
    end: str = BACKTEST_END,
    delisted_symbols: Iterable[str] = (),
    selection_log: list[dict[str, Any]] | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Run fixed-weight periods, applying turnover cost on the next session."""
    available_symbols = [symbol for symbol in symbols if symbol in prices.columns]
    if not available_symbols:
        return pd.Series(dtype="float64"), pd.Series(dtype="float64")
    subset = prices.loc[:end, available_symbols].copy()
    daily_returns = build_daily_returns(subset)
    dates = _rebalance_dates(daily_returns.index, frequency)
    all_returns = pd.Series(0.0, index=daily_returns.index, name="return")
    turnovers = pd.Series(0.0, index=daily_returns.index, name="turnover")
    previous_weights = pd.Series(dtype="float64")
    eligible = set(subset.columns)
    for position, rebalance_date in enumerate(dates):
        next_date = dates[position + 1] if position + 1 < len(dates) else daily_returns.index[-1]
        segment = daily_returns.loc[(daily_returns.index > rebalance_date) & (daily_returns.index <= next_date)]
        if segment.empty:
            continue
        # A delisted ticker is no longer eligible when its source history has no quote on the signal date.
        valid_at_close = subset.loc[rebalance_date].dropna().index
        current_weights = select_momentum_weights(
            subset,
            rebalance_date,
            eligible.intersection(valid_at_close),
            portfolio_size,
            lookback_sessions,
        )
        if selection_log is not None and rebalance_date >= pd.Timestamp(start):
            selected_delisted = sorted(set(current_weights.index).intersection(delisted_symbols))
            selection_log.append({
                "rebalance_date": rebalance_date,
                "selected_count": int(len(current_weights)),
                "selected_delisted_count": len(selected_delisted),
                "selected_delisted_symbols": selected_delisted,
            })
        all_symbols = sorted(set(previous_weights.index).union(current_weights.index))
        traded_weight = current_weights.reindex(all_symbols, fill_value=0.0).sub(
            previous_weights.reindex(all_symbols, fill_value=0.0)
        ).abs().sum()
        period_returns, ending_weights = compound_fixed_shares(
            segment.reindex(columns=all_symbols, fill_value=0.0),
            current_weights,
            cost_bps,
            float(traded_weight),
        )
        first_day = period_returns.index[0]
        all_returns.loc[period_returns.index] = period_returns
        turnovers.loc[first_day] = traded_weight
        previous_weights = ending_weights[ending_weights > 0]
    return all_returns.loc[start:end], turnovers.loc[start:end]


def summarize_returns(returns: pd.Series) -> dict[str, float]:
    """Calculate annualized return, Sharpe ratio, and maximum drawdown."""
    if returns.empty:
        return {"total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    equity = (1.0 + returns).cumprod()
    years = len(returns) / 252.0
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else -1.0
    volatility = float(returns.std(ddof=1))
    sharpe = float(math.sqrt(252.0) * returns.mean() / volatility) if volatility > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    return {
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
    }
