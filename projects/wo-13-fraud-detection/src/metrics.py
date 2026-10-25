"""Classification, threshold, and asymmetric cost metrics."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score


def ranking_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    """Calculate PR-AUC and ROC-AUC from fraud probabilities."""

    return {
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
    }


def threshold_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    false_positive_cost: float,
    false_negative_cost: float,
) -> dict[str, float | int]:
    """Calculate confusion counts, rates, and assumed cost at one threshold."""

    predictions = (probabilities >= threshold).astype(np.int8)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    false_positive_rate = fp / (fp + tn) if fp + tn else 0.0
    total_cost = fp * false_positive_cost + fn * false_negative_cost
    return {
        "threshold": float(threshold),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "precision": float(precision),
        "recall": float(recall),
        "false_positive_rate": float(false_positive_rate),
        "total_cost": float(total_cost),
        "cost_per_transaction": float(total_cost / len(y_true)),
    }


def threshold_sweep(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: Iterable[float],
    false_positive_cost: float,
    false_negative_cost: float,
) -> pd.DataFrame:
    """Evaluate operating metrics for each unique requested threshold."""

    rows = [
        threshold_metrics(
            y_true,
            probabilities,
            threshold,
            false_positive_cost,
            false_negative_cost,
        )
        for threshold in sorted(set(float(value) for value in thresholds))
    ]
    return pd.DataFrame.from_records(rows)


def select_cost_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: Iterable[float],
    false_positive_cost: float,
    false_negative_cost: float,
) -> tuple[float, pd.DataFrame]:
    """Select the lowest validation cost, breaking ties toward higher precision."""

    sweep = threshold_sweep(
        y_true,
        probabilities,
        thresholds,
        false_positive_cost,
        false_negative_cost,
    )
    ranked = sweep.sort_values(
        ["total_cost", "precision", "threshold"],
        ascending=[True, False, False],
    )
    return float(ranked.iloc[0]["threshold"]), sweep
