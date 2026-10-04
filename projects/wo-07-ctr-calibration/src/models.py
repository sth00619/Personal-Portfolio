"""LightGBM baseline fitted only to the training partition."""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.data import CATEGORICAL_COLUMNS


RANDOM_SEED = 7
TREE_COUNT = 120
LEAF_COUNT = 31
LEARNING_RATE = 0.05
MIN_CHILD_SAMPLES = 50
THREAD_COUNT = 4


def fit_baseline(features: pd.DataFrame, labels: np.ndarray) -> lgb.LGBMClassifier:
    """Fit a fixed LightGBM configuration without test data."""
    model = lgb.LGBMClassifier(
        n_estimators=TREE_COUNT,
        num_leaves=LEAF_COUNT,
        learning_rate=LEARNING_RATE,
        min_child_samples=MIN_CHILD_SAMPLES,
        random_state=RANDOM_SEED,
        n_jobs=THREAD_COUNT,
        verbosity=-1,
    )
    model.fit(features, labels, categorical_feature=list(CATEGORICAL_COLUMNS))
    return model
