"""Model fitting and evaluation helpers for WO-14."""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from .config import ExperimentConfig


def fit_model(
    x_reference: pd.DataFrame,
    y_reference: pd.Series,
    config: ExperimentConfig,
) -> LGBMClassifier:
    """Fit a fixed LightGBM model so only feature policy changes."""

    model = LGBMClassifier(
        objective="binary",
        n_estimators=config.n_estimators,
        learning_rate=config.learning_rate,
        num_leaves=config.num_leaves,
        min_child_samples=config.min_child_samples,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=config.random_seed,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(x_reference, y_reference)
    return model


def evaluate_model(
    model: LGBMClassifier,
    x_comparison: pd.DataFrame,
    y_comparison: pd.Series,
) -> dict[str, float]:
    """Return holdout discrimination metrics from model probabilities."""

    probabilities = model.predict_proba(x_comparison)[:, 1]
    return {
        "roc_auc": float(roc_auc_score(y_comparison, probabilities)),
        "pr_auc": float(average_precision_score(y_comparison, probabilities)),
    }


def feature_importance_table(
    model: LGBMClassifier,
    features: list[str],
    variant: str,
) -> pd.DataFrame:
    """Return normalized gain importance for audit-friendly model inspection."""

    gain = np.asarray(model.booster_.feature_importance(importance_type="gain"), dtype=float)
    total = gain.sum()
    normalized = gain / total if total else gain
    return pd.DataFrame(
        {"variant": variant, "feature": features, "gain_importance": normalized}
    ).sort_values("gain_importance", ascending=False)
