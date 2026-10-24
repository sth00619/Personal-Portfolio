"""Tests for leakage-safe feature construction and segmentation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import assign_intermittency, build_feature_frame


def calendar_fixture(days: int) -> pd.DataFrame:
    """Create the calendar fields required by the feature builder."""

    return pd.DataFrame(
        {
            "d": [f"d_{index + 1}" for index in range(days)],
            "wday": (np.arange(days) % 7) + 1,
            "month": np.ones(days, dtype=int),
            "snap_CA": np.zeros(days, dtype=int),
            "event_name_1": [np.nan] * days,
        }
    )


def test_features_ignore_sales_inside_forecast_horizon() -> None:
    """Changing unknown horizon sales must not alter target-day features."""

    base = np.arange(120, dtype=np.float32).reshape(1, -1)
    changed = base.copy()
    target_index = 100
    changed[:, target_index - 27 : target_index] = 99_999.0
    calendar = calendar_fixture(base.shape[1])
    target_days = np.array([target_index])
    first = build_feature_frame(base, np.array(["item"]), calendar, target_days)
    second = build_feature_frame(changed, np.array(["item"]), calendar, target_days)
    feature_columns = [column for column in first if column != "target"]
    pd.testing.assert_frame_equal(first[feature_columns], second[feature_columns])


def test_intermittency_excludes_structural_prelaunch_zeros() -> None:
    """Segment zero share must start at each series' first positive sale."""

    values = np.array([[0, 0, 1, 0, 1, 0], [0, 0, 1, 1, 1, 1]], dtype=float)
    segments = assign_intermittency(values, np.array(["a", "b"]), 6, 0.5)
    assert segments.set_index("item_id").loc["a", "segment"] == "intermittent"
    assert segments.set_index("item_id").loc["b", "segment"] == "regular"
