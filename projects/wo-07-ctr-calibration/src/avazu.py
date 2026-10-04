"""Leakage-safe features and temporal partitions for Avazu CTR calibration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from data.prepare_avazu import EXPECTED_COLUMNS, EXPECTED_DAYS


LABEL = "click"
HOUR = "hour"
RAW_CATEGORIES = tuple(
    column for column in EXPECTED_COLUMNS if column not in ("id", LABEL, HOUR)
)
HOUR_FEATURE = "hour_of_day"
WEEKDAY_FEATURE = "weekday"
FEATURE_COLUMNS = (*RAW_CATEGORIES, HOUR_FEATURE, WEEKDAY_FEATURE)
TRAIN_DAYS = EXPECTED_DAYS[:6]
CALIBRATION_DAYS = EXPECTED_DAYS[6:8]
TEST_DAYS = EXPECTED_DAYS[8:]
MIN_CATEGORY_COUNT = 20
MAX_CATEGORIES_PER_FEATURE = 512
MISSING_TOKEN = "__MISSING__"
OTHER_TOKEN = "__OTHER__"
MODEL_TREES = 160
MODEL_LEAVES = 31
MODEL_MIN_CHILD = 100
MODEL_LEARNING_RATE = 0.05
MODEL_SEED = 7
MODEL_THREADS = 4
BOOTSTRAP_REPEATS = 400
BOOTSTRAP_SEED = 71
BOOTSTRAP_LOWER = 0.025
BOOTSTRAP_UPPER = 0.975
PROBABILITY_EPSILON = 1e-15


def load_sample(path: Path) -> pd.DataFrame:
    """Load only the sampled training labels, hours, and categorical context."""
    dtypes = {name: "string[pyarrow]" for name in (*RAW_CATEGORIES, HOUR)}
    dtypes[LABEL] = "int8"
    frame = pd.read_csv(
        path, compression="gzip", usecols=[LABEL, HOUR, *RAW_CATEGORIES],
        dtype=dtypes, low_memory=False,
    )
    if frame.empty or not frame[LABEL].isin((0, 1)).all():
        raise ValueError("Sample has missing or invalid click labels")
    frame["day"] = frame[HOUR].str.slice(0, 6)
    if tuple(sorted(frame["day"].unique())) != EXPECTED_DAYS:
        raise ValueError("Sample does not cover the declared ten days")
    return frame


@dataclass(frozen=True)
class AvazuSplit:
    """Keep train, calibration, and test on disjoint chronological days."""

    train: pd.DataFrame
    calibration: pd.DataFrame
    test: pd.DataFrame


def chronological_split(frame: pd.DataFrame) -> AvazuSplit:
    """Reserve the final two days exclusively for evaluation."""
    days = tuple(sorted(frame["day"].unique()))
    if days != EXPECTED_DAYS:
        raise ValueError("Unexpected Avazu days")
    train = frame.loc[frame["day"].isin(TRAIN_DAYS)].copy()
    calibration = frame.loc[frame["day"].isin(CALIBRATION_DAYS)].copy()
    test = frame.loc[frame["day"].isin(TEST_DAYS)].copy()
    if min(len(train), len(calibration), len(test)) == 0:
        raise ValueError("Empty temporal partition")
    return AvazuSplit(train, calibration, test)


@dataclass
class AvazuFeatures:
    """Learn categorical vocabularies only from training days."""

    vocabularies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fitted: bool = False

    def fit(self, train: pd.DataFrame) -> AvazuFeatures:
        """Keep frequent values without seeing calibration or test context."""
        if self.fitted:
            raise RuntimeError("Feature mapping can only be fitted once")
        for column in RAW_CATEGORIES:
            observed = train[column].fillna(MISSING_TOKEN)
            counts = observed.value_counts()
            selected = counts[counts >= MIN_CATEGORY_COUNT]
            ordered = sorted(
                selected.index.tolist(), key=lambda value: (-int(selected[value]), str(value))
            )
            self.vocabularies[column] = tuple(
                value for value in ordered if value != MISSING_TOKEN
            )[:MAX_CATEGORIES_PER_FEATURE]
        self.fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Map future unseen and rare values to one fixed fallback category."""
        if not self.fitted:
            raise RuntimeError("Feature mapping must be fitted on train")
        features = pd.DataFrame(index=frame.index)
        for column in RAW_CATEGORIES:
            values = frame[column].fillna(MISSING_TOKEN)
            categories = (OTHER_TOKEN, MISSING_TOKEN, *self.vocabularies[column])
            mapped = values.where(values.isin(categories[1:]), OTHER_TOKEN)
            features[column] = pd.Categorical(mapped, categories=categories)
        hour = frame[HOUR].str.slice(6, 8)
        features[HOUR_FEATURE] = pd.Categorical(
            hour, categories=tuple(f"{value:02d}" for value in range(24))
        )
        day_to_weekday = {
            day: str(datetime.strptime("20" + day, "%Y%m%d").weekday())
            for day in EXPECTED_DAYS
        }
        features[WEEKDAY_FEATURE] = pd.Categorical(
            frame["day"].map(day_to_weekday),
            categories=tuple(str(value) for value in range(7)),
        )
        if features.isna().any().any():
            raise ValueError("Feature conversion introduced missing categories")
        return features


def fit_avazu_baseline(features: pd.DataFrame, labels: np.ndarray) -> lgb.LGBMClassifier:
    """Fit a fixed LightGBM setting without calibration or test labels."""
    model = lgb.LGBMClassifier(
        n_estimators=MODEL_TREES,
        num_leaves=MODEL_LEAVES,
        min_child_samples=MODEL_MIN_CHILD,
        learning_rate=MODEL_LEARNING_RATE,
        random_state=MODEL_SEED,
        n_jobs=MODEL_THREADS,
        verbosity=-1,
    )
    model.fit(features, labels, categorical_feature=list(FEATURE_COLUMNS))
    return model


def _ece(labels: np.ndarray, probabilities: np.ndarray, bins: int) -> float:
    """Compute equal-width ECE from bin totals without constructing frames."""
    bucket = np.minimum((probabilities * bins).astype(np.int32), bins - 1)
    predicted = np.bincount(bucket, weights=probabilities, minlength=bins)
    observed = np.bincount(bucket, weights=labels, minlength=bins)
    return float(np.abs(predicted - observed).sum() / len(labels))


def paired_bootstrap(
    labels: np.ndarray, predictions: dict[str, np.ndarray], days: np.ndarray,
    bins: int, repeats: int = BOOTSTRAP_REPEATS,
) -> dict[str, dict[str, float | list[float]]]:
    """Stratify by held-out day and bound paired calibration improvements."""
    if bins <= 0 or repeats <= 0 or len(labels) != len(days):
        raise ValueError("Invalid bootstrap dimensions")
    if set(predictions) != {"baseline", "platt", "isotonic"}:
        raise ValueError("Three matched model predictions are required")
    n = len(labels)
    if any(len(values) != n for values in predictions.values()):
        raise ValueError("Bootstrap predictions must align with labels")
    losses = {
        name: -labels * np.log(np.clip(values, PROBABILITY_EPSILON, 1))
        - (1 - labels) * np.log(np.clip(1 - values, PROBABILITY_EPSILON, 1))
        for name, values in predictions.items()
    }
    groups = [np.flatnonzero(days == day) for day in np.unique(days)]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = {
        name: {
            "ece": np.empty(repeats, dtype=float),
            "log_loss": np.empty(repeats, dtype=float),
        }
        for name in ("platt", "isotonic")
    }
    for repetition in range(repeats):
        sample = np.concatenate([
            rng.choice(group, size=len(group), replace=True) for group in groups
        ])
        sampled_labels = labels[sample]
        baseline_ece = _ece(sampled_labels, predictions["baseline"][sample], bins)
        for name in sampled:
            sampled[name]["ece"][repetition] = baseline_ece - _ece(
                sampled_labels, predictions[name][sample], bins
            )
            sampled[name]["log_loss"][repetition] = np.mean(
                losses["baseline"][sample] - losses[name][sample]
            )
    outputs: dict[str, dict[str, float | list[float]]] = {}
    for name in sampled:
        outputs[name] = {
            "ece_reduction": _ece(labels, predictions["baseline"], bins)
            - _ece(labels, predictions[name], bins),
            "ece_reduction_95_ci": [
                float(np.quantile(sampled[name]["ece"], BOOTSTRAP_LOWER)),
                float(np.quantile(sampled[name]["ece"], BOOTSTRAP_UPPER)),
            ],
            "log_loss_reduction": float(np.mean(losses["baseline"] - losses[name])),
            "log_loss_reduction_95_ci": [
                float(np.quantile(sampled[name]["log_loss"], BOOTSTRAP_LOWER)),
                float(np.quantile(sampled[name]["log_loss"], BOOTSTRAP_UPPER)),
            ],
        }
    return outputs
