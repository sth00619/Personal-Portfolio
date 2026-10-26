"""Load, validate, aggregate, and split Home Credit tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


APPLICATION_EXPECTED_SHAPE = (307_511, 122)
BUREAU_EXPECTED_ROWS = 1_716_428
PREVIOUS_EXPECTED_ROWS = 1_670_214
SENTINEL_DAY = 365_243

BUREAU_NUMERIC_COLUMNS = (
    "DAYS_CREDIT",
    "CREDIT_DAY_OVERDUE",
    "DAYS_CREDIT_ENDDATE",
    "DAYS_ENDDATE_FACT",
    "AMT_CREDIT_MAX_OVERDUE",
    "CNT_CREDIT_PROLONG",
    "AMT_CREDIT_SUM",
    "AMT_CREDIT_SUM_DEBT",
    "AMT_CREDIT_SUM_LIMIT",
    "AMT_CREDIT_SUM_OVERDUE",
    "DAYS_CREDIT_UPDATE",
    "AMT_ANNUITY",
)
PREVIOUS_NUMERIC_COLUMNS = (
    "AMT_ANNUITY",
    "AMT_APPLICATION",
    "AMT_CREDIT",
    "AMT_DOWN_PAYMENT",
    "AMT_GOODS_PRICE",
    "HOUR_APPR_PROCESS_START",
    "RATE_DOWN_PAYMENT",
    "DAYS_DECISION",
    "CNT_PAYMENT",
    "DAYS_FIRST_DRAWING",
    "DAYS_FIRST_DUE",
    "DAYS_LAST_DUE_1ST_VERSION",
    "DAYS_LAST_DUE",
    "DAYS_TERMINATION",
)


@dataclass(frozen=True)
class ProxySplit:
    """Hold row positions for a deterministic proxy-order holdout."""

    reference: np.ndarray
    comparison: np.ndarray


def _require_columns(frame: pd.DataFrame, required: set[str], table: str) -> None:
    """Raise a useful error when a source table does not match the contract."""

    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{table} is missing required columns: {sorted(missing)}")


def load_application(path: Path) -> pd.DataFrame:
    """Load and validate the labeled application table."""

    frame = pd.read_csv(path)
    _require_columns(frame, {"SK_ID_CURR", "TARGET"}, "application_train")
    if frame.shape != APPLICATION_EXPECTED_SHAPE:
        raise ValueError(
            f"application_train shape={frame.shape}, expected={APPLICATION_EXPECTED_SHAPE}"
        )
    if frame["SK_ID_CURR"].duplicated().any():
        raise ValueError("application_train has duplicate SK_ID_CURR values")
    if set(frame["TARGET"].dropna().unique()) != {0, 1}:
        raise ValueError("TARGET must contain exactly 0 and 1")
    return frame


def _flatten_aggregations(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Flatten a pandas multi-index aggregation into stable uppercase names."""

    frame.columns = [
        f"{prefix}_{column}_{stat}".upper() for column, stat in frame.columns
    ]
    return frame.reset_index()


def aggregate_bureau(path: Path, validate_rows: bool = True) -> pd.DataFrame:
    """Aggregate credit-bureau rows to one row per current application."""

    columns = [
        "SK_ID_CURR",
        "CREDIT_ACTIVE",
        "CREDIT_TYPE",
        *BUREAU_NUMERIC_COLUMNS,
    ]
    bureau = pd.read_csv(path, usecols=columns)
    _require_columns(bureau, set(columns), "bureau")
    if validate_rows and len(bureau) != BUREAU_EXPECTED_ROWS:
        raise ValueError(f"bureau rows={len(bureau)}, expected={BUREAU_EXPECTED_ROWS}")

    numeric = bureau.groupby("SK_ID_CURR", sort=False)[list(BUREAU_NUMERIC_COLUMNS)].agg(
        ["mean", "min", "max", "sum"]
    )
    aggregated = _flatten_aggregations(numeric, "BUREAU")
    counts = bureau.groupby("SK_ID_CURR", sort=False).size().rename("BUREAU_RECORD_COUNT")
    active_ratio = (
        bureau["CREDIT_ACTIVE"].eq("Active").groupby(bureau["SK_ID_CURR"]).mean()
    ).rename("BUREAU_ACTIVE_RATIO")
    type_count = bureau.groupby("SK_ID_CURR", sort=False)["CREDIT_TYPE"].nunique().rename(
        "BUREAU_CREDIT_TYPE_NUNIQUE"
    )
    aggregated = aggregated.join(counts, on="SK_ID_CURR")
    aggregated = aggregated.join(active_ratio, on="SK_ID_CURR")
    aggregated = aggregated.join(type_count, on="SK_ID_CURR")
    if aggregated["SK_ID_CURR"].duplicated().any():
        raise AssertionError("bureau aggregation is not one row per SK_ID_CURR")
    return aggregated


def aggregate_previous(path: Path, validate_rows: bool = True) -> pd.DataFrame:
    """Aggregate previous applications to one row per current application."""

    columns = ["SK_ID_CURR", "NAME_CONTRACT_STATUS", *PREVIOUS_NUMERIC_COLUMNS]
    previous = pd.read_csv(path, usecols=columns)
    _require_columns(previous, set(columns), "previous_application")
    if validate_rows and len(previous) != PREVIOUS_EXPECTED_ROWS:
        raise ValueError(
            f"previous_application rows={len(previous)}, expected={PREVIOUS_EXPECTED_ROWS}"
        )
    day_columns = [column for column in PREVIOUS_NUMERIC_COLUMNS if column.startswith("DAYS_")]
    previous.loc[:, day_columns] = previous.loc[:, day_columns].replace(SENTINEL_DAY, np.nan)

    numeric = previous.groupby("SK_ID_CURR", sort=False)[
        list(PREVIOUS_NUMERIC_COLUMNS)
    ].agg(["mean", "min", "max", "sum"])
    aggregated = _flatten_aggregations(numeric, "PREV")
    counts = previous.groupby("SK_ID_CURR", sort=False).size().rename("PREV_RECORD_COUNT")
    status = previous["NAME_CONTRACT_STATUS"]
    status_rates = {}
    for label in ("Approved", "Refused", "Canceled", "Unused offer"):
        name = label.upper().replace(" ", "_")
        status_rates[f"PREV_STATUS_{name}_RATIO"] = (
            status.eq(label).groupby(previous["SK_ID_CURR"]).mean()
        )
    aggregated = aggregated.join(counts, on="SK_ID_CURR")
    for name, rates in status_rates.items():
        aggregated = aggregated.join(rates.rename(name), on="SK_ID_CURR")
    if aggregated["SK_ID_CURR"].duplicated().any():
        raise AssertionError("previous aggregation is not one row per SK_ID_CURR")
    return aggregated


def join_related_tables(
    application: pd.DataFrame,
    bureau: pd.DataFrame,
    previous: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join one-row-per-customer aggregates without changing application rows."""

    joined = application.merge(bureau, on="SK_ID_CURR", how="left", validate="one_to_one")
    joined = joined.merge(previous, on="SK_ID_CURR", how="left", validate="one_to_one")
    if len(joined) != len(application):
        raise AssertionError("related-table joins changed application row count")
    return joined


def make_proxy_order_split(
    frame: pd.DataFrame,
    id_column: str = "SK_ID_CURR",
    train_fraction: float = 0.8,
) -> ProxySplit:
    """Split by anonymous application ID order as a non-temporal stress-test proxy."""

    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must lie strictly between zero and one")
    order = np.argsort(frame[id_column].to_numpy(), kind="stable")
    boundary = int(len(order) * train_fraction)
    reference = order[:boundary]
    comparison = order[boundary:]
    if len(reference) == 0 or len(comparison) == 0:
        raise ValueError("proxy split produced an empty partition")
    return ProxySplit(reference=reference, comparison=comparison)


def encode_train_comparison(
    frame: pd.DataFrame,
    split: ProxySplit,
    features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Encode categories with reference-only vocabularies and preserve missing numerics."""

    reference = frame.iloc[split.reference][features].copy()
    comparison = frame.iloc[split.comparison][features].copy()
    categorical = reference.select_dtypes(include=["object", "category"]).columns.tolist()
    for column in categorical:
        reference_values = reference[column].fillna("__MISSING__").astype(str)
        comparison_values = comparison[column].fillna("__MISSING__").astype(str)
        mapping = {value: index for index, value in enumerate(sorted(reference_values.unique()))}
        reference[column] = reference_values.map(mapping).astype("float32")
        comparison[column] = comparison_values.map(mapping).fillna(-1).astype("float32")
    numeric = [column for column in features if column not in categorical]
    reference.loc[:, numeric] = reference.loc[:, numeric].replace([np.inf, -np.inf], np.nan)
    comparison.loc[:, numeric] = comparison.loc[:, numeric].replace([np.inf, -np.inf], np.nan)
    return reference.astype("float32"), comparison.astype("float32"), categorical

