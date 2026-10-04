"""Fit Platt and isotonic mappings using calibration predictions only."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


PROBABILITY_EPSILON = 1e-6
PLATT_MAX_ITER = 1000
PREFERRED_METHOD = "platt"


def as_probabilities(values: np.ndarray) -> np.ndarray:
    """Validate a one-dimensional array of finite probabilities."""
    probabilities = np.asarray(values, dtype=float)
    if probabilities.ndim != 1 or not np.isfinite(probabilities).all():
        raise ValueError("Expected one-dimensional finite probabilities")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Probabilities must be within [0, 1]")
    return probabilities


def log_odds(probabilities: np.ndarray) -> np.ndarray:
    """Convert bounded probabilities to numerically safe log odds."""
    bounded = np.clip(as_probabilities(probabilities), PROBABILITY_EPSILON, 1 - PROBABILITY_EPSILON)
    return np.log(bounded / (1 - bounded)).reshape(-1, 1)


@dataclass(frozen=True)
class Calibrators:
    """Store fitted post-hoc mappings that never see test labels."""

    platt: LogisticRegression
    isotonic: IsotonicRegression

    def predict(self, probabilities: np.ndarray) -> dict[str, np.ndarray]:
        """Map base probabilities to both calibrated probabilities."""
        base = as_probabilities(probabilities)
        return {
            "baseline": base,
            "platt": self.platt.predict_proba(log_odds(base))[:, 1],
            "isotonic": np.asarray(self.isotonic.predict(base), dtype=float),
        }


def fit_calibrators(probabilities: np.ndarray, labels: np.ndarray) -> Calibrators:
    """Fit Platt scaling and isotonic regression on calibration data."""
    base = as_probabilities(probabilities)
    truth = np.asarray(labels, dtype=int)
    if len(base) != len(truth) or len(np.unique(truth)) != 2:
        raise ValueError("Calibration needs matched probabilities and both label classes")
    platt = LogisticRegression(max_iter=PLATT_MAX_ITER)
    platt.fit(log_odds(base), truth)
    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(base, truth)
    return Calibrators(platt, isotonic)
