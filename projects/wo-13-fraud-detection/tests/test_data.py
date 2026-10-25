"""Tests for temporal splitting and training-only preprocessing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import encode_split, high_missing_columns, make_splits


def frame_fixture() -> pd.DataFrame:
    """Create a small chronological fraud dataset for split tests."""

    return pd.DataFrame(
        {
            "TransactionID": np.arange(20),
            "TransactionDT": np.arange(20) * 10,
            "isFraud": [0, 0, 0, 1, 0] * 4,
            "ProductCD": ["W", "C"] * 10,
            "mostly_missing": [np.nan] * 15 + [1.0] * 5,
        }
    )


def test_temporal_holdout_is_strictly_later() -> None:
    """Every temporal holdout timestamp must follow every training timestamp."""

    frame = frame_fixture()
    splits = make_splits(frame, "isFraud", "TransactionDT", 0.8, 13)
    assert frame.iloc[splits.time_train]["TransactionDT"].max() < frame.iloc[
        splits.time_test
    ]["TransactionDT"].min()
    assert set(splits.time_train).isdisjoint(set(splits.time_test))


def test_missingness_and_categories_are_fit_on_training_rows() -> None:
    """Holdout values must not influence missing-feature or category fitting."""

    frame = frame_fixture()
    train_indices = np.arange(10)
    test_indices = np.arange(10, 20)
    missing = high_missing_columns(
        frame, train_indices, ["ProductCD", "mostly_missing"], 0.9
    )
    assert list(missing.index) == ["mostly_missing"]
    frame.loc[test_indices, "ProductCD"] = "unseen"
    encoded = encode_split(
        frame,
        train_indices,
        test_indices,
        ["TransactionDT", "ProductCD"],
        "isFraud",
    )
    assert set(encoded.x_train["ProductCD"]) == {0, 1}
    assert set(encoded.x_test["ProductCD"]) == {2}
