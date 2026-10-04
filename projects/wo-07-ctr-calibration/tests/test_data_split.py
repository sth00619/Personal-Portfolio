"""Temporal split and source schema safeguards."""

from __future__ import annotations

import pytest

from src.data import (
    CALIBRATION_DAY,
    TEST_DAY,
    TRAIN_DAYS,
    validate_day_order,
)


def test_fixed_dates_are_disjoint_and_ascending() -> None:
    """The configured split must move strictly forward by date."""
    validate_day_order(TRAIN_DAYS, CALIBRATION_DAY, TEST_DAY)


@pytest.mark.parametrize(
    ("train_days", "calibration_day", "test_day"),
    [
        (("2015-02-15",), "2015-02-15", "2015-02-18"),
        (("2015-02-17",), "2015-02-16", "2015-02-18"),
        (("2015-02-15",), "2015-02-18", "2015-02-17"),
    ],
)
def test_overlap_or_reverse_order_is_rejected(
    train_days: tuple[str, ...], calibration_day: str, test_day: str
) -> None:
    """No label from a later or duplicate day can enter training."""
    with pytest.raises(ValueError):
        validate_day_order(train_days, calibration_day, test_day)
