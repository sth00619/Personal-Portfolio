"""Unit tests for Population Stability Index calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.stability import feature_psi_table, population_stability_index


def test_identical_distribution_has_zero_psi() -> None:
    """An unchanged numeric population should have zero PSI."""

    values = pd.Series(np.arange(100, dtype=float))
    assert population_stability_index(values, values.copy()) == 0.0


def test_shift_and_missing_bucket_increase_psi() -> None:
    """A shifted population with additional missingness should be unstable."""

    reference = pd.Series([0.0] * 50 + [1.0] * 50)
    comparison = pd.Series([0.0] * 10 + [1.0] * 40 + [np.nan] * 50)
    assert population_stability_index(reference, comparison) > 0.25


def test_feature_table_labels_aggregate_sources() -> None:
    """Feature evidence should distinguish application and joined sources."""

    frame = pd.DataFrame(
        {
            "AGE": [1, 2, 3, 4],
            "BUREAU_COUNT": [1, 1, 2, 2],
            "PREV_COUNT": [0, 1, 0, 1],
        }
    )
    table = feature_psi_table(frame, np.array([0, 1]), np.array([2, 3]), list(frame))
    sources = dict(zip(table["feature"], table["source"], strict=True))
    assert sources == {
        "AGE": "application",
        "BUREAU_COUNT": "bureau_aggregate",
        "PREV_COUNT": "previous_aggregate",
    }

