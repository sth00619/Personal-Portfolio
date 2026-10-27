"""Download and cache KRX listing metadata and daily price histories."""

from __future__ import annotations

import re
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd

from wo24.config import (
    DATA_CACHE,
    DELISTED_MAX_YEAR,
    DELISTED_MIN_YEAR,
    DOWNLOAD_START,
    MANIFEST_PATH,
    POPULATION_SUMMARY_PATH,
    CURRENT_SAMPLE_SIZE_PER_MARKET,
    DELISTED_SAMPLE_SIZE,
)

COMMON_CODE = re.compile(r"\d{6}")
EXCLUDED_DELISTING_REASONS = ("피흡수합병", "완전자회사", "전액 중도 환수", "상환", "존속기간 만료")


def _evenly_spaced(frame: pd.DataFrame, size: int) -> pd.DataFrame:
    """Select a deterministic spread of rows from a sorted listing."""
    if len(frame) <= size:
        return frame.copy()
    positions = pd.Series(range(size), dtype="float64")
    indexes = (positions * (len(frame) - 1) / (size - 1)).round().astype(int)
    return frame.iloc[indexes.to_list()].copy()


def select_universe() -> pd.DataFrame:
    """Create matched, reproducible samples from current and delisted KRX shares."""
    current = fdr.StockListing("KRX")
    current = current[
        current["Market"].isin(["KOSPI", "KOSDAQ"])
        & current["Code"].astype(str).str.fullmatch(COMMON_CODE)
        & current["MarketId"].isin(["STK", "KSQ"])
        & ~current["Name"].fillna("").str.contains(r"우(?:[A-Z])?$", regex=True)
    ].copy()
    current["Code"] = current["Code"].astype(str).str.zfill(6)
    current["MarketCap"] = pd.to_numeric(current["Marcap"], errors="coerce")
    current = current.dropna(subset=["MarketCap"]).sort_values(["Market", "MarketCap", "Code"])
    current_population_size = len(current)
    current_sample = pd.concat(
        [_evenly_spaced(group, CURRENT_SAMPLE_SIZE_PER_MARKET) for _, group in current.groupby("Market")],
        ignore_index=True,
    )
    current_sample = current_sample.rename(columns={"Code": "Symbol"})
    current_sample["Universe"] = "current"
    current_sample["ListingDate"] = pd.NaT
    current_sample["DelistingDate"] = pd.NaT
    current_sample["Reason"] = ""

    delisted = fdr.StockListing("KRX-DELISTING")
    delisted = delisted[
        delisted["Market"].isin(["KOSPI", "KOSDAQ"])
        & delisted["Symbol"].astype(str).str.fullmatch(COMMON_CODE)
        & (delisted["SecuGroup"] == "주권")
        & ~delisted["Name"].fillna("").str.contains(r"우(?:[A-Z])?$", regex=True)
        & delisted["DelistingDate"].between(
            f"{DELISTED_MIN_YEAR}-01-01", f"{DELISTED_MAX_YEAR}-12-31"
        )
    ].copy()
    eligible_population_size = len(delisted)
    reason = delisted["Reason"].fillna("")
    excluded_event_mask = reason.apply(lambda value: any(term in value for term in EXCLUDED_DELISTING_REASONS))
    excluded_event_size = int(excluded_event_mask.sum())
    delisted = delisted[~excluded_event_mask]
    delisted = delisted.sort_values(["DelistingDate", "Symbol"])
    delisted_sample_pool_size = len(delisted)
    delisted_sample = _evenly_spaced(delisted, DELISTED_SAMPLE_SIZE)
    delisted_sample["Universe"] = "delisted"

    fields = ["Symbol", "Name", "Market", "Universe", "ListingDate", "DelistingDate", "Reason"]
    manifest = pd.concat([current_sample[fields], delisted_sample[fields]], ignore_index=True)
    manifest["Symbol"] = manifest["Symbol"].astype(str).str.zfill(6)
    population_summary = pd.DataFrame([
        {"population": "current_common_shares", "eligible_count": current_population_size,
         "sampled_count": len(current_sample), "not_sampled_count": current_population_size - len(current_sample)},
        {"population": "delisted_common_shares_before_reason_filter", "eligible_count": eligible_population_size,
         "sampled_count": delisted_sample_pool_size, "not_sampled_count": 0},
        {"population": "delisted_merger_redemption_or_maturity_reasons_excluded", "eligible_count": excluded_event_size,
         "sampled_count": 0, "not_sampled_count": excluded_event_size},
        {"population": "delisted_candidate_pool_after_reason_filter", "eligible_count": delisted_sample_pool_size,
         "sampled_count": len(delisted_sample), "not_sampled_count": delisted_sample_pool_size - len(delisted_sample)},
    ])
    POPULATION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    population_summary.to_csv(POPULATION_SUMMARY_PATH, index=False)
    return manifest.drop_duplicates(subset=["Symbol", "Universe"]).sort_values(["Universe", "Symbol"])


def download_prices(manifest: pd.DataFrame, end: str) -> pd.DataFrame:
    """Fetch per-symbol price histories, caching source responses outside Git."""
    DATA_CACHE.mkdir(parents=True, exist_ok=True)
    series: list[pd.Series] = []
    failures: list[dict[str, str]] = []
    for row in manifest.itertuples(index=False):
        cache_path = DATA_CACHE / f"{row.Universe}_{row.Symbol}.csv"
        try:
            if cache_path.exists():
                prices = pd.read_csv(cache_path, parse_dates=["Date"], index_col="Date")
            else:
                prices = fdr.DataReader(row.Symbol, DOWNLOAD_START, end)
                if prices.empty or "Close" not in prices.columns:
                    failures.append({"Symbol": row.Symbol, "Universe": row.Universe, "Reason": "empty_price_response"})
                    continue
                prices = prices[["Close"]].rename(columns={"Close": row.Symbol})
                prices.index.name = "Date"
                prices.to_csv(cache_path)
        except Exception as error:
            failures.append({"Symbol": row.Symbol, "Universe": row.Universe, "Reason": type(error).__name__})
            continue
        if "Close" in prices.columns:
            prices = prices.rename(columns={"Close": row.Symbol})
        if row.Symbol in prices.columns:
            series.append(prices[row.Symbol].rename(row.Symbol))
    if not series:
        raise RuntimeError("No price histories were returned by the configured source.")
    prices = pd.concat(series, axis=1).sort_index()
    prices = prices.loc[~prices.index.duplicated(keep="last")]
    if failures:
        failure_path = DATA_CACHE.parent / "processed" / "download_failures.csv"
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(failures).to_csv(failure_path, index=False)
    return prices


def prepare_data(end: str = "2025-01-10", refresh_universe: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select the experiment sample, fetch prices, and save the lightweight manifest."""
    if MANIFEST_PATH.exists() and not refresh_universe:
        manifest = pd.read_csv(MANIFEST_PATH, dtype={"Symbol": str})
    else:
        manifest = select_universe()
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(MANIFEST_PATH, index=False)
    prices = download_prices(manifest, end)
    return manifest, prices
