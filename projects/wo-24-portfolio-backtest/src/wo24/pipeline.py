"""Execute the WO-24 data collection, backtests, and result export."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import pandas as pd

from wo24.backtest import run_backtest, summarize_returns
from wo24.config import (
    BACKTEST_END,
    BACKTEST_START,
    ATTRIBUTION_COST_BPS,
    CURRENT_COST_BPS,
    MONTHLY_COST_BPS,
    POPULATION_SUMMARY_PATH,
    QUARTERLY_COST_BPS,
    RESULTS_DIR,
)
from wo24.data import MANIFEST_PATH, prepare_data


def run_pipeline(download_only: bool = False, refresh_universe: bool = False) -> None:
    """Run two-universe comparisons and export compact, reproducible results."""
    manifest, prices = prepare_data(refresh_universe=refresh_universe)
    print(f"Downloaded price panel: {prices.shape[0]} sessions x {prices.shape[1]} symbols", flush=True)
    print(f"Manifest: {len(manifest)} rows ({manifest['Universe'].value_counts().to_dict()})", flush=True)
    if download_only:
        print(f"Data ready; manifest saved to {MANIFEST_PATH}")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    current_symbols = manifest.loc[manifest["Universe"] == "current", "Symbol"].tolist()
    delisted_symbols = manifest.loc[manifest["Universe"] == "delisted", "Symbol"].tolist()
    scenarios = [
        ("current_only", current_symbols, "monthly", cost)
        for cost in CURRENT_COST_BPS
    ] + [
        ("delisted_included", current_symbols + delisted_symbols, "monthly", cost)
        for cost in MONTHLY_COST_BPS
    ] + [
        ("delisted_included", current_symbols + delisted_symbols, "quarterly", QUARTERLY_COST_BPS)
    ]
    rows: list[dict[str, object]] = []
    returns_by_scenario: dict[str, pd.Series] = {}
    delisted_events: list[dict[str, object]] = []
    for universe, symbols, frequency, cost in scenarios:
        label = f"{universe}_{frequency}_{cost}bps"
        selection_log = (
            delisted_events
            if universe == "delisted_included" and frequency == "monthly" and cost == ATTRIBUTION_COST_BPS
            else None
        )
        returns, turnover = run_backtest(
            prices,
            symbols,
            cost,
            frequency,
            delisted_symbols=delisted_symbols if universe == "delisted_included" else (),
            selection_log=selection_log,
        )
        metrics = summarize_returns(returns)
        rows.append({
            "universe": universe,
            "rebalance": frequency,
            "cost_bps_per_traded_value": cost,
            "symbols_requested": len(symbols),
            "symbols_with_prices": len(set(symbols).intersection(prices.columns)),
            "mean_monthly_turnover": float(turnover.resample("ME").sum().mean()),
            **metrics,
        })
        returns_by_scenario[label] = returns
        print(f"{label}: CAGR={metrics['cagr']:.4f}, Sharpe={metrics['sharpe']:.3f}, MDD={metrics['max_drawdown']:.3f}", flush=True)

    summary = pd.DataFrame(rows)
    summary.to_csv(RESULTS_DIR / "scenario_summary.csv", index=False)
    coverage = manifest.groupby("Universe")["Symbol"].agg(manifest_count="count").reset_index()
    available = prices.columns.to_series().groupby(manifest.set_index("Symbol")["Universe"]).size()
    coverage["price_histories"] = coverage["Universe"].map(available).fillna(0).astype(int)
    coverage["missing_price_histories"] = coverage["manifest_count"] - coverage["price_histories"]
    coverage.to_csv(RESULTS_DIR / "universe_coverage.csv", index=False)
    selected_delisted_symbols = Counter(
        symbol
        for event in delisted_events
        for symbol in event["selected_delisted_symbols"]
    )
    delisted_attribution = {
        "monthly_rebalance_events": len(delisted_events),
        "events_with_at_least_one_delisted_holding": sum(
            int(event["selected_delisted_count"] > 0) for event in delisted_events
        ),
        "delisted_ticker_months_in_portfolio": int(sum(selected_delisted_symbols.values())),
        "distinct_delisted_tickers_selected": len(selected_delisted_symbols),
        "selected_delisted_ticker_months": dict(sorted(selected_delisted_symbols.items())),
    }
    (RESULTS_DIR / "delisted_selection_attribution.json").write_text(
        json.dumps(delisted_attribution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    daily_returns = pd.DataFrame(returns_by_scenario).loc[BACKTEST_START:BACKTEST_END]
    daily_returns.to_csv(RESULTS_DIR / "daily_returns.csv", index_label="date")
    source_metadata = {
        "listing_source": "FinanceDataReader KRX and KRX-DELISTING listing providers",
        "price_source": "FinanceDataReader default Korean equity price source (Naver Finance)",
        "universe_manifest": "data/universe_manifest.csv",
        "sample_note": "Deterministic, stratified ticker sample; not a full-market point-in-time panel.",
        "price_panel_shape": [int(prices.shape[0]), int(prices.shape[1])],
        "manifest_rows": int(len(manifest)),
        "delisted_manifest_rows": int((manifest["Universe"] == "delisted").sum()),
        "population_summary_path": str(POPULATION_SUMMARY_PATH.relative_to(POPULATION_SUMMARY_PATH.parents[1])),
    }
    (RESULTS_DIR / "run_metadata.json").write_text(
        json.dumps(source_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Results exported to {RESULTS_DIR}")


def main() -> None:
    """Parse the command line and launch the pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true", help="Fetch data and write the ticker manifest only.")
    parser.add_argument("--refresh-universe", action="store_true", help="Refresh the generated ticker manifest from listing providers.")
    args = parser.parse_args()
    try:
        run_pipeline(download_only=args.download_only, refresh_universe=args.refresh_universe)
    except Exception as error:
        print(f"WO-24 pipeline failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
