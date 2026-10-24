"""Unit tests for quantile forecast metrics."""

from __future__ import annotations

import numpy as np

from src.metrics import interval_coverage, mean_pinball_loss, pinball_loss, rearrange_quantiles


def test_pinball_loss_penalizes_direction_asymmetrically() -> None:
    """High quantiles must penalize underprediction more than overprediction."""

    actual = np.array([10.0])
    under = pinball_loss(actual, np.array([8.0]), 0.9)
    over = pinball_loss(actual, np.array([12.0]), 0.9)
    assert np.isclose(under, 1.8)
    assert np.isclose(over, 0.2)


def test_coverage_reports_explicit_numerator_and_denominator() -> None:
    """Coverage must retain its sample-count denominator."""

    coverage, covered, total = interval_coverage(
        np.array([0.0, 2.0, 5.0]),
        np.array([0.0, 1.0, 1.0]),
        np.array([0.0, 3.0, 4.0]),
    )
    assert coverage == 2 / 3
    assert (covered, total) == (2, 3)


def test_mean_pinball_rejects_wrong_matrix_shape() -> None:
    """Metric input must contain one column per requested quantile."""

    with np.testing.assert_raises(ValueError):
        mean_pinball_loss(np.array([1.0]), np.array([[1.0, 2.0]]), (0.1, 0.5, 0.9))


def test_rearrangement_removes_crossing_and_reports_rate() -> None:
    """Monotone rearrangement must preserve values while ordering quantiles."""

    raw = np.array([[3.0, 2.0, 4.0], [1.0, 2.0, 3.0]])
    ordered, crossing_rate = rearrange_quantiles(raw)
    assert crossing_rate == 0.5
    assert np.array_equal(ordered[0], np.array([2.0, 3.0, 4.0]))

