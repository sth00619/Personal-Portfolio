"""Unit tests for fraud threshold and cost calculations."""

from __future__ import annotations

import numpy as np

from src.metrics import select_cost_threshold, threshold_metrics


def test_threshold_metrics_preserve_all_confusion_counts() -> None:
    """False positives and false negatives must remain in the cost denominator."""

    actual = np.array([0, 0, 1, 1], dtype=np.int8)
    probability = np.array([0.1, 0.7, 0.4, 0.9])
    metrics = threshold_metrics(actual, probability, 0.5, 1.0, 10.0)
    assert (metrics["tn"], metrics["fp"], metrics["fn"], metrics["tp"]) == (
        1,
        1,
        1,
        1,
    )
    assert metrics["total_cost"] == 11.0


def test_cost_ratio_changes_selected_threshold() -> None:
    """Higher missed-fraud cost must permit a lower operating threshold."""

    actual = np.array([0, 0, 0, 1, 1], dtype=np.int8)
    probability = np.array([0.05, 0.15, 0.4, 0.2, 0.8])
    thresholds = (0.1, 0.3, 0.5)
    low_fn_threshold, _ = select_cost_threshold(
        actual, probability, thresholds, 1.0, 1.0
    )
    high_fn_threshold, _ = select_cost_threshold(
        actual, probability, thresholds, 1.0, 10.0
    )
    assert high_fn_threshold < low_fn_threshold

