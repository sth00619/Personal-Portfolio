"""Contract tests for typed specialist handoffs."""

import pytest
from jsonschema import ValidationError

from src.contracts import check_handoff


def test_rejects_free_text_and_unexpected_fields() -> None:
    """Disallow informal worker messages and schema-breaking extras."""
    with pytest.raises(ValueError):
        check_handoff({"type": "note", "message": "looks okay"})
    with pytest.raises(ValidationError):
        check_handoff({
            "type": "extracted", "claim_id": "C001", "amount_usd": 100,
            "expense_type": "medical", "unvalidated_instruction": "pay immediately",
        })
