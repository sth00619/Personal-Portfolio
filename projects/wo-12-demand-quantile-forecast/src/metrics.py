"""Metrics for point and quantile demand forecasts."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, quantile: float) -> float:
    """Return mean pinball loss at one requested quantile."""

    residual = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.mean(np.maximum(quantile * residual, (quantile - 1.0) * residual)))


def mean_pinball_loss(
    y_true: np.ndarray,
    predictions: np.ndarray,
    quantiles: Sequence[float],
) -> float:
    """Average pinball loss equally across observations and quantiles."""

    matrix = np.asarray(predictions, dtype=float)
    if matrix.shape != (len(y_true), len(quantiles)):
        raise ValueError("prediction matrix shape must be observations by quantiles")
    losses = [
        pinball_loss(y_true, matrix[:, column], quantile)
        for column, quantile in enumerate(quantiles)
    ]
    return float(np.mean(losses))


def interval_coverage(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> tuple[float, int, int]:
    """Return inclusive coverage plus covered and total observation counts."""

    actual = np.asarray(y_true, dtype=float)
    inside = (actual >= np.asarray(lower, dtype=float)) & (
        actual <= np.asarray(upper, dtype=float)
    )
    covered = int(inside.sum())
    total = int(inside.size)
    return covered / total, covered, total


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return root mean squared error for point forecasts."""

    residual = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean(np.square(residual))))


def rearrange_quantiles(predictions: np.ndarray) -> tuple[np.ndarray, float]:
    """Sort row-wise quantiles and report the raw crossing rate."""

    matrix = np.asarray(predictions, dtype=float)
    crossing = np.any(np.diff(matrix, axis=1) < 0, axis=1)
    return np.sort(matrix, axis=1), float(np.mean(crossing))

