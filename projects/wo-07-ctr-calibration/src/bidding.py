"""Hypothetical bid-value estimation error, without auction costs."""

from __future__ import annotations

import numpy as np

from src.calibration import as_probabilities


CLICK_VALUE_KRW = 1_000.0


def bidding_proxy(
    labels: np.ndarray, probabilities: np.ndarray, click_value: float = CLICK_VALUE_KRW
) -> dict[str, float]:
    """Compare summed hypothetical click values with observed click value."""
    truth = np.asarray(labels, dtype=int)
    scores = as_probabilities(probabilities)
    if len(truth) != len(scores) or click_value <= 0 or not np.isin(truth, [0, 1]).all():
        raise ValueError("Invalid bidding proxy inputs")
    estimated = float(click_value * scores.sum())
    observed = float(click_value * truth.sum())
    bias = estimated - observed
    return {
        "click_value_krw": float(click_value),
        "estimated_click_value_krw": estimated,
        "observed_click_value_krw": observed,
        "aggregate_bias_krw": bias,
        "absolute_error_proxy_krw": abs(bias),
        "mean_hypothetical_bid_krw": float(click_value * scores.mean()),
    }
