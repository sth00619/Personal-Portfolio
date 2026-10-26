"""Create controlled model-version accuracy changes for detector experiments."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


BoolArray = NDArray[np.bool_]
StringArray = NDArray[np.str_]


def inject_regression(
    baseline_correct: BoolArray,
    segments: StringArray,
    target_segment: str,
    eligible_segments: Sequence[str],
    regression_points: float,
    rng: np.random.Generator,
) -> BoolArray:
    """Lower target accuracy and offset the same errors in a control segment."""
    if not 0 < regression_points < 1:
        raise ValueError("regression_points must be between zero and one")
    if target_segment not in eligible_segments:
        raise ValueError("target segment must be eligible")
    version = baseline_correct.copy()
    target = np.flatnonzero(segments == target_segment)
    target_correct = target[baseline_correct[target]]
    changes = int(round(len(target) * regression_points))
    if len(target_correct) < changes:
        raise ValueError("Not enough correct target rows to inject the requested drop")
    degrade = rng.choice(target_correct, size=changes, replace=False)
    version[degrade] = False

    control = np.flatnonzero(
        np.isin(segments, [value for value in eligible_segments if value != target_segment])
    )
    control_errors = control[~baseline_correct[control]]
    if len(control_errors) < changes:
        raise ValueError("Not enough control errors to preserve global accuracy")
    improve = rng.choice(control_errors, size=changes, replace=False)
    version[improve] = True
    return version


def inject_neutral_version(
    baseline_correct: BoolArray,
    segments: StringArray,
    eligible_segments: Sequence[str],
    swap_fraction: float,
    rng: np.random.Generator,
) -> BoolArray:
    """Swap equal correct/error counts within each segment to preserve accuracy."""
    if not 0 < swap_fraction < 0.5:
        raise ValueError("swap_fraction must be between zero and one half")
    version = baseline_correct.copy()
    for segment in eligible_segments:
        rows = np.flatnonzero(segments == segment)
        correct = rows[baseline_correct[rows]]
        incorrect = rows[~baseline_correct[rows]]
        swaps = int(round(len(rows) * swap_fraction))
        if min(len(correct), len(incorrect)) < swaps:
            raise ValueError(f"Insufficient correct/error examples in segment {segment}")
        to_error = rng.choice(correct, size=swaps, replace=False)
        to_correct = rng.choice(incorrect, size=swaps, replace=False)
        version[to_error] = False
        version[to_correct] = True
    return version


def holm_rejections(p_values: NDArray[np.float64], alpha: float) -> NDArray[np.bool_]:
    """Apply Holm's step-down family-wise error correction row by row."""
    if p_values.ndim != 2 or not 0 < alpha < 1:
        raise ValueError("Expected a 2D p-value matrix and alpha between zero and one")
    rows, tests = p_values.shape
    order = np.argsort(p_values, axis=1)
    sorted_values = np.take_along_axis(p_values, order, axis=1)
    sorted_rejections = np.zeros((rows, tests), dtype=bool)
    active = np.ones(rows, dtype=bool)
    for rank in range(tests):
        active &= sorted_values[:, rank] <= alpha / (tests - rank)
        sorted_rejections[:, rank] = active
    rejections = np.zeros_like(sorted_rejections)
    np.put_along_axis(rejections, order, sorted_rejections, axis=1)
    return rejections


def paired_bootstrap_upper_bounds(
    differences: NDArray[np.int8],
    confidence: float,
    repetitions: int,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    """Return row-wise percentile upper bounds for paired mean differences."""
    if differences.ndim != 2 or not 0 < confidence < 1 or repetitions < 100:
        raise ValueError("Invalid paired-bootstrap input")
    sample_size = differences.shape[1]
    p_negative = np.mean(differences == -1, axis=1)
    p_positive = np.mean(differences == 1, axis=1)
    p_other = np.maximum(0.0, 1.0 - p_negative)
    conditional_positive = np.divide(
        p_positive,
        p_other,
        out=np.zeros_like(p_positive),
        where=p_other > 0,
    )
    negative_counts = rng.binomial(
        sample_size,
        p_negative[:, None],
        size=(differences.shape[0], repetitions),
    )
    positive_counts = rng.binomial(
        sample_size - negative_counts,
        conditional_positive[:, None],
        size=(differences.shape[0], repetitions),
    )
    bootstrap_means = (positive_counts - negative_counts) / sample_size
    return np.quantile(bootstrap_means, confidence, axis=1)
