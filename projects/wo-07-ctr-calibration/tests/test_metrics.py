"""Calibration metric definitions and numeric boundaries."""

from __future__ import annotations

import numpy as np
import pytest

from src.metrics import calibration_bins, equal_count_curve, evaluate, expected_calibration_error


def test_perfect_and_reversed_probabilities() -> None:
    """ECE distinguishes perfect calibration from severe reversal."""
    labels = np.array([0, 1])
    assert expected_calibration_error(labels, np.array([0.0, 1.0])) == 0.0
    assert expected_calibration_error(labels, np.array([1.0, 0.0])) == 1.0


def test_equal_width_boundaries_empty_bins_and_weighting() -> None:
    """A boundary belongs to its right bin and p=1 to the final bin."""
    labels = np.array([0, 1, 1, 0])
    scores = np.array([0.0, 0.1, 0.1, 1.0])
    bins = calibration_bins(labels, scores)
    assert bins[0]["count"] == 1
    assert bins[1]["count"] == 2
    assert bins[2]["count"] == 0
    assert bins[2]["mean_prediction"] is None
    assert bins[9]["count"] == 1
    assert expected_calibration_error(labels, scores) == pytest.approx(0.7)


def test_logloss_is_safe_at_probability_limits() -> None:
    """Exact zero and one cannot produce infinite loss."""
    measured = evaluate(np.array([0, 1]), np.array([1.0, 0.0]))
    assert np.isfinite(measured["log_loss"])
    with pytest.raises(ValueError):
        evaluate(np.array([0, 1]), np.array([-0.1, 1.0]))


def test_equal_count_curve_accounts_for_every_observation() -> None:
    """Plot bins must cover the same observations as the measured test set."""
    curve = equal_count_curve(np.array([0, 1, 0, 1, 0]), np.linspace(0, 1, 5), 2)
    assert sum(bucket["count"] for bucket in curve) == 5
