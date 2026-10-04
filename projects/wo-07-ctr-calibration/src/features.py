"""Train-only preprocessing for numeric and sparse categorical features."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS


MIN_CATEGORY_COUNT = 10
MAX_CATEGORIES_PER_FEATURE = 512
MISSING_TOKEN = "__MISSING__"
RARE_TOKEN = "__RARE__"
UNKNOWN_TOKEN = "__UNKNOWN__"
RESERVED_TOKENS = (MISSING_TOKEN, RARE_TOKEN, UNKNOWN_TOKEN)


@dataclass
class TrainOnlyFeatures:
    """Keep fitted medians and category vocabularies from train data only."""

    medians: dict[str, float] = field(default_factory=dict)
    seen_categories: dict[str, frozenset[str]] = field(default_factory=dict)
    frequent_categories: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fitted: bool = False

    def fit(self, train: pd.DataFrame) -> TrainOnlyFeatures:
        """Learn missing-value and rare-category rules on training rows."""
        if self.fitted:
            raise RuntimeError("Feature rules are immutable after fitting")
        for column in NUMERIC_COLUMNS:
            numeric = pd.to_numeric(train[column], errors="raise")
            median = numeric.median()
            self.medians[column] = float(median) if pd.notna(median) else 0.0
        for column in CATEGORICAL_COLUMNS:
            values = train[column].astype("string").fillna(MISSING_TOKEN)
            observed = values[values != MISSING_TOKEN]
            counts = observed.value_counts()
            selected = counts[counts >= MIN_CATEGORY_COUNT]
            ordered = sorted(selected.index.tolist(), key=lambda item: (-int(selected[item]), item))
            self.seen_categories[column] = frozenset(observed.unique().tolist())
            self.frequent_categories[column] = tuple(
                ordered[:MAX_CATEGORIES_PER_FEATURE]
            )
        self.fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply frozen rules and mark future-only values as unknown."""
        if not self.fitted:
            raise RuntimeError("Fit on train before transforming")
        result = pd.DataFrame(index=frame.index)
        for column in NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(frame[column], errors="raise").fillna(
                self.medians[column]
            ).astype("float32")
        for column in CATEGORICAL_COLUMNS:
            values = frame[column].astype("string").fillna(MISSING_TOKEN)
            frequent = self.frequent_categories[column]
            seen = self.seen_categories[column]
            mapped = np.where(
                values.eq(MISSING_TOKEN),
                MISSING_TOKEN,
                np.where(values.isin(frequent), values, np.where(values.isin(seen), RARE_TOKEN, UNKNOWN_TOKEN)),
            )
            categories = [*RESERVED_TOKENS, *frequent]
            result[column] = pd.Categorical(mapped, categories=categories)
        return result
