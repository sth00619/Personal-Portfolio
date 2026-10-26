"""Check the controlled version mutations and family-wise correction."""

import numpy as np

from scripts.regression import holm_rejections, inject_neutral_version, inject_regression


def test_neutral_version_preserves_accuracy_in_each_segment() -> None:
    """A no-regression version may change decisions but keeps segment accuracy."""
    correct = np.array([True, True, True, False, False, False] * 3)
    segments = np.repeat(np.array(["0", "1", "4"]), 6)
    version = inject_neutral_version(
        correct, segments, ("0", "1", "4"), 1 / 6, np.random.default_rng(4)
    )
    assert int(version.sum()) == int(correct.sum())
    for segment in ("0", "1", "4"):
        mask = segments == segment
        assert int(version[mask].sum()) == int(correct[mask].sum())


def test_regression_lowers_target_but_preserves_global_accuracy() -> None:
    """The synthetic B version masks its target drop with a control improvement."""
    correct = np.array([True] * 80 + [False] * 20 + [True] * 60 + [False] * 40)
    segments = np.array(["0"] * 100 + ["1"] * 100)
    version = inject_regression(
        correct, segments, "0", ("0", "1"), 0.05, np.random.default_rng(7)
    )
    target = segments == "0"
    assert int(version.sum()) == int(correct.sum())
    assert np.isclose(correct[target].mean() - version[target].mean(), 0.05)


def test_holm_correction_stops_after_first_failed_rank() -> None:
    """Holm rejects only hypotheses passing every earlier step-down bound."""
    p_values = np.array([[0.001, 0.02, 0.04], [0.02, 0.03, 0.04]])
    rejected = holm_rejections(p_values, alpha=0.05)
    assert rejected.tolist() == [[True, True, True], [False, False, False]]
