"""IEEE-CIS loading, split construction, and leakage-safe encoding."""

from __future__ import annotations

import gc
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


CARD_PATTERN = re.compile(r"^card[1-6]$")
ADDRESS_PATTERN = re.compile(r"^addr[1-2]$")
IDENTITY_PATTERN = re.compile(r"^id_(1[2-9]|2[0-9]|3[0-8])$")


@dataclass(frozen=True)
class DataSplits:
    """Store row indices for temporal and random holdout comparisons."""

    time_train: np.ndarray
    time_test: np.ndarray
    random_train: np.ndarray
    random_test: np.ndarray


@dataclass(frozen=True)
class EncodedSplit:
    """Store encoded train and test matrices with labels and categorical names."""

    x_train: pd.DataFrame
    y_train: np.ndarray
    x_test: pd.DataFrame
    y_test: np.ndarray
    categorical_columns: tuple[str, ...]


def optimize_numeric_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    """Downcast numeric columns to reduce memory without changing missingness."""

    for column in frame.select_dtypes(include=["float64"]).columns:
        frame[column] = frame[column].astype(np.float32)
    for column in frame.select_dtypes(include=["int64"]).columns:
        minimum = int(frame[column].min())
        maximum = int(frame[column].max())
        if np.iinfo(np.int8).min <= minimum and maximum <= np.iinfo(np.int8).max:
            frame[column] = frame[column].astype(np.int8)
        elif np.iinfo(np.int32).min <= minimum and maximum <= np.iinfo(np.int32).max:
            frame[column] = frame[column].astype(np.int32)
    return frame


def load_joined_data(transaction_path: Path, identity_path: Path) -> pd.DataFrame:
    """Load transaction and identity tables and left join on TransactionID."""

    transaction = pd.read_csv(transaction_path, low_memory=False)
    identity = pd.read_csv(identity_path, low_memory=False)
    frame = transaction.merge(
        identity,
        on="TransactionID",
        how="left",
        validate="one_to_one",
    )
    del transaction, identity
    gc.collect()
    return optimize_numeric_dtypes(frame)


def feature_columns(frame: pd.DataFrame, id_column: str, target_column: str) -> list[str]:
    """Return predictors while removing the row identifier and label."""

    return [column for column in frame.columns if column not in (id_column, target_column)]


def categorical_columns(frame: pd.DataFrame, features: list[str]) -> list[str]:
    """Identify official IEEE-CIS categorical fields among retained predictors."""

    columns: list[str] = []
    for column in features:
        is_string = pd.api.types.is_object_dtype(frame[column].dtype)
        is_official_code = bool(
            CARD_PATTERN.match(column)
            or ADDRESS_PATTERN.match(column)
            or IDENTITY_PATTERN.match(column)
        )
        if is_string or is_official_code:
            columns.append(column)
    return columns


def make_splits(
    frame: pd.DataFrame,
    target_column: str,
    time_column: str,
    train_fraction: float,
    random_seed: int,
) -> DataSplits:
    """Create matched-size chronological and stratified random holdouts."""

    order = np.argsort(frame[time_column].to_numpy(), kind="stable")
    cut = int(len(order) * train_fraction)
    time_train = order[:cut]
    time_test = order[cut:]
    all_indices = np.arange(len(frame), dtype=np.int64)
    random_train, random_test = train_test_split(
        all_indices,
        train_size=train_fraction,
        stratify=frame[target_column].to_numpy(),
        random_state=random_seed,
    )
    return DataSplits(
        time_train=np.asarray(time_train, dtype=np.int64),
        time_test=np.asarray(time_test, dtype=np.int64),
        random_train=np.asarray(random_train, dtype=np.int64),
        random_test=np.asarray(random_test, dtype=np.int64),
    )


def high_missing_columns(
    frame: pd.DataFrame,
    train_indices: np.ndarray,
    features: list[str],
    threshold: float,
) -> pd.Series:
    """Measure missingness on training rows only and return high-missing rates."""

    rates = frame.iloc[train_indices][features].isna().mean()
    return rates.loc[rates > threshold].sort_values(ascending=False)


def _category_levels(
    frame: pd.DataFrame,
    train_indices: np.ndarray,
    columns: list[str],
) -> dict[str, pd.Index]:
    """Fit category levels using training rows without inspecting holdout values."""

    levels: dict[str, pd.Index] = {}
    train = frame.iloc[train_indices]
    for column in columns:
        levels[column] = pd.Index(pd.unique(train[column].dropna()))
    return levels


def _encode_matrix(
    frame: pd.DataFrame,
    indices: np.ndarray,
    features: list[str],
    category_levels: dict[str, pd.Index],
) -> pd.DataFrame:
    """Encode one row slice as float32 values and training-fitted category codes."""

    matrix = frame.iloc[indices][features].copy()
    for column, levels in category_levels.items():
        codes = pd.Categorical(matrix[column], categories=levels).codes.astype(np.int32)
        codes[codes < 0] = len(levels)
        matrix[column] = codes
    numeric_columns = [column for column in features if column not in category_levels]
    matrix[numeric_columns] = matrix[numeric_columns].astype(np.float32)
    return matrix.copy()


def encode_split(
    frame: pd.DataFrame,
    train_indices: np.ndarray,
    test_indices: np.ndarray,
    features: list[str],
    target_column: str,
) -> EncodedSplit:
    """Fit categorical vocabularies on training rows and encode a holdout split."""

    categories = categorical_columns(frame, features)
    levels = _category_levels(frame, train_indices, categories)
    return EncodedSplit(
        x_train=_encode_matrix(frame, train_indices, features, levels),
        y_train=frame.iloc[train_indices][target_column].to_numpy(dtype=np.int8),
        x_test=_encode_matrix(frame, test_indices, features, levels),
        y_test=frame.iloc[test_indices][target_column].to_numpy(dtype=np.int8),
        categorical_columns=tuple(categories),
    )


def temporal_inner_split(
    time_train_indices: np.ndarray,
    inner_train_fraction: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Split the chronological training window into fit and threshold-validation rows."""

    cut = int(len(time_train_indices) * inner_train_fraction)
    return time_train_indices[:cut], time_train_indices[cut:]

