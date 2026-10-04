"""Train-only preprocessing and future category safeguards."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS
from src.features import (
    MISSING_TOKEN,
    RARE_TOKEN,
    UNKNOWN_TOKEN,
    TrainOnlyFeatures,
)


def example_frame(categories: list[str | None], numerics: list[float | None]) -> pd.DataFrame:
    """Construct a minimal frame with the real feature schema."""
    rows = len(categories)
    frame = pd.DataFrame({column: numerics for column in NUMERIC_COLUMNS})
    for column in CATEGORICAL_COLUMNS:
        frame[column] = categories[:rows]
    return frame


def test_rare_unknown_missing_and_median_are_train_only() -> None:
    """Future-only values never change train vocabulary or fill values."""
    train = example_frame(["common"] * 11 + ["rare", None], [1.0] * 12 + [None])
    future = example_frame(["rare", "new", None], [None, 999.0, None])
    transformer = TrainOnlyFeatures().fit(train)
    before_seen = transformer.seen_categories[CATEGORICAL_COLUMNS[0]]
    mapped = transformer.transform(future)
    column = CATEGORICAL_COLUMNS[0]
    assert mapped[column].astype(str).tolist() == [RARE_TOKEN, UNKNOWN_TOKEN, MISSING_TOKEN]
    assert mapped[NUMERIC_COLUMNS[0]].tolist() == [1.0, 999.0, 1.0]
    assert transformer.seen_categories[column] == before_seen
    assert "new" not in before_seen
    with pytest.raises(RuntimeError):
        transformer.fit(future)
