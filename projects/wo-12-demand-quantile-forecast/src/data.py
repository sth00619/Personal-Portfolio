"""Memory-bounded M5 loading and leakage-safe feature construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


METADATA_COLUMNS = (
    "id",
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id",
)
LAGS = (28, 35, 42, 56)
ROLLING_WINDOWS = (28, 56)
MIN_HISTORY = max(max(LAGS), 28 + max(ROLLING_WINDOWS) - 1)
FORECAST_GAP = 28


@dataclass(frozen=True)
class M5Subset:
    """Store the selected M5 sales matrix and matching calendar rows."""

    item_ids: np.ndarray
    values: np.ndarray
    day_labels: tuple[str, ...]
    calendar: pd.DataFrame


def day_number(day_label: str) -> int:
    """Parse an M5 day label such as d_1941 into its integer component."""

    return int(day_label.removeprefix("d_"))


def load_subset(
    sales_path: Path,
    calendar_path: Path,
    store_id: str,
    category_id: str,
    chunk_rows: int,
) -> M5Subset:
    """Load one store-category slice without materializing all M5 rows."""

    selected: list[pd.DataFrame] = []
    for chunk in pd.read_csv(sales_path, chunksize=chunk_rows):
        mask = (chunk["store_id"] == store_id) & (chunk["cat_id"] == category_id)
        if mask.any():
            selected.append(chunk.loc[mask].copy())
    if not selected:
        raise ValueError(f"No rows found for store={store_id}, category={category_id}")

    frame = pd.concat(selected, ignore_index=True)
    day_labels = tuple(
        sorted(
            (column for column in frame.columns if column.startswith("d_")),
            key=day_number,
        )
    )
    calendar = pd.read_csv(calendar_path)
    calendar = calendar.set_index("d").loc[list(day_labels)].reset_index()
    return M5Subset(
        item_ids=frame["item_id"].astype(str).to_numpy(),
        values=frame.loc[:, day_labels].to_numpy(dtype=np.float32),
        day_labels=day_labels,
        calendar=calendar,
    )


def _known_rolling(values: np.ndarray, target_index: int, window: int) -> np.ndarray:
    """Compute a window ending 28 days before a forecast target."""

    end = target_index - FORECAST_GAP + 1
    start = end - window
    return values[:, start:end]


def build_feature_frame(
    values: np.ndarray,
    item_ids: np.ndarray,
    calendar: pd.DataFrame,
    target_indices: np.ndarray,
    include_target: bool = True,
) -> pd.DataFrame:
    """Build direct multi-step features using only origin-known sales values."""

    if target_indices.size == 0:
        raise ValueError("target_indices must contain at least one day")
    if int(target_indices.min()) < MIN_HISTORY:
        raise ValueError(f"target index must be at least {MIN_HISTORY}")

    n_items = values.shape[0]
    frames: list[pd.DataFrame] = []
    encoded_items = pd.Categorical(item_ids).codes.astype(np.int32)
    for target_index in target_indices:
        target_day = int(target_index)
        cal = calendar.iloc[target_day]
        payload: dict[str, np.ndarray] = {
            "item_code": encoded_items,
            "target_index": np.full(n_items, target_day, dtype=np.int32),
            "wday": np.full(n_items, int(cal["wday"]), dtype=np.int8),
            "month": np.full(n_items, int(cal["month"]), dtype=np.int8),
            "snap_ca": np.full(n_items, int(cal["snap_CA"]), dtype=np.int8),
            "event": np.full(
                n_items,
                int(pd.notna(cal.get("event_name_1"))),
                dtype=np.int8,
            ),
        }
        for lag in LAGS:
            payload[f"lag_{lag}"] = values[:, target_day - lag]
        for window in ROLLING_WINDOWS:
            known = _known_rolling(values, target_day, window)
            payload[f"known_mean_{window}"] = known.mean(axis=1)
            payload[f"known_std_{window}"] = known.std(axis=1)
            payload[f"known_zero_share_{window}"] = (known == 0).mean(axis=1)
        payload["item_id"] = item_ids
        if include_target:
            payload["target"] = values[:, target_day]
        frames.append(pd.DataFrame(payload))
    frame = pd.concat(frames, ignore_index=True)
    frame["item_code"] = frame["item_code"].astype("category")
    return frame


def assign_intermittency(
    values: np.ndarray,
    item_ids: np.ndarray,
    train_end: int,
    threshold: float,
) -> pd.DataFrame:
    """Classify series by zero share after each item's first observed sale."""

    records: list[dict[str, object]] = []
    for item_id, series in zip(item_ids, values[:, :train_end], strict=True):
        nonzero = np.flatnonzero(series > 0)
        active = series[nonzero[0] :] if nonzero.size else series
        zero_share = float(np.mean(active == 0))
        records.append(
            {
                "item_id": str(item_id),
                "zero_share": zero_share,
                "segment": "intermittent" if zero_share >= threshold else "regular",
            }
        )
    return pd.DataFrame.from_records(records)

