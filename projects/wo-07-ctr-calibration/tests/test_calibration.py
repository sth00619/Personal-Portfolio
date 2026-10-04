"""Calibration is fitted on its own partition and predicts without labels."""

from __future__ import annotations

import inspect

import numpy as np

from src.calibration import Calibrators, fit_calibrators


def test_calibrators_accept_only_probabilities_at_prediction() -> None:
    """The inference API offers no test-label fitting path."""
    calibration_scores = np.array([0.05, 0.15, 0.25, 0.75, 0.85, 0.95])
    calibration_labels = np.array([0, 0, 0, 1, 1, 1])
    fitted = fit_calibrators(calibration_scores, calibration_labels)
    assert list(inspect.signature(Calibrators.predict).parameters) == ["self", "probabilities"]
    predicted = fitted.predict(np.array([0.0, 0.5, 1.0]))
    assert set(predicted) == {"baseline", "platt", "isotonic"}
    assert all(np.isfinite(values).all() and ((0 <= values) & (values <= 1)).all() for values in predicted.values())
