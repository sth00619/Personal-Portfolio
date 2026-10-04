"""Manual check of the hypothetical bid-value proxy."""

from __future__ import annotations

import numpy as np

from src.bidding import bidding_proxy


def test_proxy_is_aggregate_prediction_error() -> None:
    """The proxy uses assumed value, not an observed auction payment."""
    result = bidding_proxy(np.array([1, 0]), np.array([0.2, 0.3]), click_value=100.0)
    assert result["estimated_click_value_krw"] == 50.0
    assert result["observed_click_value_krw"] == 100.0
    assert result["aggregate_bias_krw"] == -50.0
    assert result["absolute_error_proxy_krw"] == 50.0
    assert result["mean_hypothetical_bid_krw"] == 25.0
