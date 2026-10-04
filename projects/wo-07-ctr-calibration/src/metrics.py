"""Probability, ranking, and calibration metrics with fixed bin semantics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import log_loss, roc_auc_score

from src.calibration import as_probabilities


ECE_BINS = 10
CURVE_BINS = 20
LOGLOSS_EPSILON = 1e-15


def calibration_bins(
    labels: np.ndarray, probabilities: np.ndarray, bin_count: int = ECE_BINS
) -> list[dict[str, float | int | None]]:
    """Build equal-width bins [left, right), with 1 included in the final bin."""
    truth = np.asarray(labels, dtype=int)
    scores = as_probabilities(probabilities)
    if len(truth) != len(scores) or len(truth) == 0 or bin_count <= 0:
        raise ValueError("Labels, probabilities, and bin count are invalid")
    if not np.isin(truth, [0, 1]).all():
        raise ValueError("Expected binary labels")
    indices = np.minimum(np.floor(scores * bin_count).astype(int), bin_count - 1)
    output: list[dict[str, float | int | None]] = []
    for index in range(bin_count):
        selected = indices == index
        count = int(selected.sum())
        output.append(
            {
                "bin": index,
                "left": index / bin_count,
                "right": (index + 1) / bin_count,
                "count": count,
                "mean_prediction": float(scores[selected].mean()) if count else None,
                "observed_rate": float(truth[selected].mean()) if count else None,
            }
        )
    return output


def expected_calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bin_count: int = ECE_BINS
) -> float:
    """Weight absolute bin gaps by sample share; empty bins contribute zero."""
    bins = calibration_bins(labels, probabilities, bin_count)
    sample_count = len(labels)
    return float(
        sum(
            int(bucket["count"]) / sample_count
            * abs(float(bucket["mean_prediction"]) - float(bucket["observed_rate"]))
            for bucket in bins
            if bucket["count"]
        )
    )


def equal_count_curve(
    labels: np.ndarray, probabilities: np.ndarray, bin_count: int = CURVE_BINS
) -> list[dict[str, float | int]]:
    """Summarize sorted predictions in nearly equal-sized bins for the plot."""
    truth = np.asarray(labels, dtype=int)
    scores = as_probabilities(probabilities)
    if len(truth) != len(scores) or len(truth) < bin_count or bin_count <= 0:
        raise ValueError("Invalid equal-count curve inputs")
    order = np.argsort(scores, kind="stable")
    return [
        {
            "bin": index,
            "count": int(len(indices)),
            "mean_prediction": float(scores[indices].mean()),
            "observed_rate": float(truth[indices].mean()),
        }
        for index, indices in enumerate(np.array_split(order, bin_count))
    ]


def evaluate(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float | int]:
    """Compute AUC, safe log loss, and fixed 10-bin ECE."""
    truth = np.asarray(labels, dtype=int)
    scores = as_probabilities(probabilities)
    if len(truth) != len(scores) or len(np.unique(truth)) != 2:
        raise ValueError("Evaluation needs matched arrays and both label classes")
    safe = np.clip(scores, LOGLOSS_EPSILON, 1 - LOGLOSS_EPSILON)
    return {
        "auc": float(roc_auc_score(truth, scores)),
        "log_loss": float(log_loss(truth, safe, labels=[0, 1])),
        "ece": expected_calibration_error(truth, scores),
        "sample_count": int(len(truth)),
    }
