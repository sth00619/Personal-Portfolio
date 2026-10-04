"""Read fixed, dated Criteo Parquet shard prefixes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


ROWS_PER_DAY = 40_000
TRAIN_DAYS = ("2015-02-15", "2015-02-16")
CALIBRATION_DAY = "2015-02-17"
TEST_DAY = "2015-02-18"
LABEL_COLUMN = "label"
NUMERIC_COLUMNS = tuple(f"integer_feature_{number}" for number in range(1, 14))
CATEGORICAL_COLUMNS = tuple(f"categorical_feature_{number}" for number in range(1, 27))
EXPECTED_COLUMNS = (LABEL_COLUMN, *NUMERIC_COLUMNS, *CATEGORICAL_COLUMNS)
BATCH_SIZE = 10_000


@dataclass(frozen=True)
class TemporalSplit:
    """Hold nonoverlapping date groups and their observations."""

    train: pd.DataFrame
    calibration: pd.DataFrame
    test: pd.DataFrame
    train_days: tuple[str, ...]
    calibration_day: str
    test_day: str


def validate_day_order(
    train_days: tuple[str, ...], calibration_day: str, test_day: str
) -> None:
    """Reject overlapping or nonascending date partitions."""
    days = (*train_days, calibration_day, test_day)
    if len(set(days)) != len(days) or tuple(sorted(days)) != days:
        raise ValueError("Expected disjoint train < calibration < test dates")


def read_prefix(path: Path, limit: int = ROWS_PER_DAY) -> pd.DataFrame:
    """Stream only the selected prefix of one Parquet shard."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    parquet = pq.ParquetFile(path)
    if tuple(parquet.schema_arrow.names) != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected Criteo schema: {path}")
    batches: list[pd.DataFrame] = []
    remaining = limit
    for batch in parquet.iter_batches(batch_size=min(BATCH_SIZE, remaining)):
        frame = batch.to_pandas()
        batches.append(frame.iloc[:remaining])
        remaining -= min(len(frame), remaining)
        if remaining == 0:
            break
    if remaining != 0:
        raise ValueError(f"Shard has fewer than {limit} rows: {path}")
    result = pd.concat(batches, ignore_index=True)
    if result[LABEL_COLUMN].isna().any() or not result[LABEL_COLUMN].isin([0, 1]).all():
        raise ValueError(f"Invalid binary labels: {path}")
    return result


def load_split(data_dir: Path, rows_per_day: int = ROWS_PER_DAY) -> TemporalSplit:
    """Load day-separated train, calibration, and untouched test data."""
    validate_day_order(TRAIN_DAYS, CALIBRATION_DAY, TEST_DAY)
    train = pd.concat(
        [read_prefix(data_dir / f"{day}.parquet", rows_per_day) for day in TRAIN_DAYS],
        ignore_index=True,
    )
    calibration = read_prefix(data_dir / f"{CALIBRATION_DAY}.parquet", rows_per_day)
    test = read_prefix(data_dir / f"{TEST_DAY}.parquet", rows_per_day)
    return TemporalSplit(train, calibration, test, TRAIN_DAYS, CALIBRATION_DAY, TEST_DAY)
