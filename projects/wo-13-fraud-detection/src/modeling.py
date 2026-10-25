"""LightGBM fitting and inference latency measurement."""

from __future__ import annotations

from time import perf_counter_ns

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from .config import ExperimentConfig
from .data import EncodedSplit


NANOSECONDS_PER_MILLISECOND = 1_000_000


def fit_model(split: EncodedSplit, config: ExperimentConfig) -> LGBMClassifier:
    """Fit a deterministic unweighted LightGBM binary classifier."""

    model = LGBMClassifier(
        objective="binary",
        n_estimators=config.n_estimators,
        learning_rate=config.learning_rate,
        num_leaves=config.num_leaves,
        min_child_samples=config.min_child_samples,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        max_bin=127,
        reg_lambda=0.1,
        random_state=config.random_seed,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(
        split.x_train,
        split.y_train,
        categorical_feature=list(split.categorical_columns),
    )
    return model


def predict_probabilities(model: LGBMClassifier, matrix: pd.DataFrame) -> np.ndarray:
    """Return positive-class fraud probabilities."""

    return np.asarray(model.predict_proba(matrix)[:, 1], dtype=float)


def measure_latency(
    model: LGBMClassifier,
    matrix: pd.DataFrame,
    sample_count: int,
    random_seed: int,
) -> dict[str, float | int]:
    """Measure batch throughput and single-row model-scoring latency."""

    model.predict_proba(matrix.iloc[:1])
    batch_start = perf_counter_ns()
    model.predict_proba(matrix)
    batch_elapsed = perf_counter_ns() - batch_start

    rng = np.random.default_rng(random_seed)
    count = min(sample_count, len(matrix))
    positions = rng.choice(len(matrix), size=count, replace=False)
    single_latencies: list[float] = []
    for position in positions:
        start = perf_counter_ns()
        model.predict_proba(matrix.iloc[[int(position)]])
        elapsed = perf_counter_ns() - start
        single_latencies.append(elapsed / NANOSECONDS_PER_MILLISECOND)
    values = np.asarray(single_latencies, dtype=float)
    return {
        "batch_rows": int(len(matrix)),
        "batch_total_ms": float(batch_elapsed / NANOSECONDS_PER_MILLISECOND),
        "batch_ms_per_row": float(
            batch_elapsed / NANOSECONDS_PER_MILLISECOND / len(matrix)
        ),
        "single_row_samples": int(count),
        "single_row_p50_ms": float(np.percentile(values, 50)),
        "single_row_p95_ms": float(np.percentile(values, 95)),
    }

