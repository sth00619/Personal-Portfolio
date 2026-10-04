"""Strict JSON Schema contracts for every worker handoff."""

from typing import Any

from jsonschema import validate

EXTRACTED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "claim_id", "amount_usd", "expense_type"],
    "properties": {
        "type": {"const": "extracted"},
        "claim_id": {"type": "string", "pattern": "^C[0-9]{3}$"},
        "amount_usd": {"type": "integer", "minimum": 1},
        "expense_type": {"type": "string", "enum": ["medical"]},
    },
    "additionalProperties": False,
}

INVESTIGATED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "covered", "invoice_present", "receipt_present", "used_supplemental"],
    "properties": {
        "type": {"const": "investigated"},
        "covered": {"type": "boolean"},
        "invoice_present": {"type": "boolean"},
        "receipt_present": {"type": "boolean"},
        "used_supplemental": {"type": "boolean"},
    },
    "additionalProperties": False,
}

REVIEWED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "recommendation", "reason"],
    "properties": {
        "type": {"const": "reviewed"},
        "recommendation": {"type": "string", "enum": ["APPROVE", "DENY", "NEEDS_INFO", "RETURN"]},
        "reason": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}

SCHEMAS: dict[str, dict[str, Any]] = {
    "extracted": EXTRACTED_SCHEMA,
    "investigated": INVESTIGATED_SCHEMA,
    "reviewed": REVIEWED_SCHEMA,
}


def check_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    """Reject free-text, unknown, or malformed inter-worker messages."""
    kind = handoff.get("type")
    if kind not in SCHEMAS:
        raise ValueError(f"Unknown handoff type: {kind!r}")
    validate(instance=handoff, schema=SCHEMAS[kind])
    return handoff
