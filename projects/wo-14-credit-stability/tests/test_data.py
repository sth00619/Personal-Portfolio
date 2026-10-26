"""Unit tests for aggregation and proxy split invariants."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data import (
    BUREAU_NUMERIC_COLUMNS,
    PREVIOUS_NUMERIC_COLUMNS,
    aggregate_bureau,
    aggregate_previous,
    make_proxy_order_split,
)


def test_proxy_split_uses_strict_id_order() -> None:
    """Reference IDs must all precede comparison IDs under the declared proxy."""

    frame = pd.DataFrame({"SK_ID_CURR": [50, 10, 40, 20, 30]})
    split = make_proxy_order_split(frame, train_fraction=0.6)
    reference_ids = frame.iloc[split.reference]["SK_ID_CURR"]
    comparison_ids = frame.iloc[split.comparison]["SK_ID_CURR"]
    assert reference_ids.max() < comparison_ids.min()
    assert set(split.reference).isdisjoint(split.comparison)


def test_aggregations_produce_one_row_per_customer(tmp_path: Path) -> None:
    """Relationship aggregations must preserve counts and unique customer keys."""

    bureau_rows = []
    for customer, amount in [(1, 100.0), (1, 200.0), (2, 50.0)]:
        row = {column: amount for column in BUREAU_NUMERIC_COLUMNS}
        row.update(
            {
                "SK_ID_CURR": customer,
                "CREDIT_ACTIVE": "Active" if amount >= 100 else "Closed",
                "CREDIT_TYPE": "Consumer credit",
            }
        )
        bureau_rows.append(row)
    bureau_path = tmp_path / "bureau.csv"
    pd.DataFrame(bureau_rows).to_csv(bureau_path, index=False)

    previous_rows = []
    for customer, amount, status in [(1, 10.0, "Approved"), (1, 30.0, "Refused"), (2, 5.0, "Approved")]:
        row = {column: amount for column in PREVIOUS_NUMERIC_COLUMNS}
        row.update({"SK_ID_CURR": customer, "NAME_CONTRACT_STATUS": status})
        previous_rows.append(row)
    previous_path = tmp_path / "previous.csv"
    pd.DataFrame(previous_rows).to_csv(previous_path, index=False)

    bureau = aggregate_bureau(bureau_path, validate_rows=False)
    previous = aggregate_previous(previous_path, validate_rows=False)
    assert bureau["SK_ID_CURR"].is_unique
    assert previous["SK_ID_CURR"].is_unique
    assert bureau.set_index("SK_ID_CURR").loc[1, "BUREAU_RECORD_COUNT"] == 2
    assert previous.set_index("SK_ID_CURR").loc[1, "PREV_RECORD_COUNT"] == 2
    assert np.isclose(
        previous.set_index("SK_ID_CURR").loc[1, "PREV_STATUS_APPROVED_RATIO"], 0.5
    )
