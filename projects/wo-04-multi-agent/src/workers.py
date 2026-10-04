"""Pure specialist workers; all routing remains with the supervisor."""

import re
from typing import Any

from .contracts import check_handoff

CLAIM_PATTERN = re.compile(r"^Claim (C\d{3}): medical expense of \$(\d+)\.$")


def extract(case: dict[str, Any]) -> dict[str, Any]:
    """Parse the synthetic claim form into a typed handoff."""
    match = CLAIM_PATTERN.fullmatch(case["claim_document"])
    if match is None or match.group(1) != case["case_id"]:
        raise ValueError("Malformed or mismatched claim form")
    return check_handoff({
        "type": "extracted",
        "claim_id": match.group(1),
        "amount_usd": int(match.group(2)),
        "expense_type": "medical",
    })


def investigate(case: dict[str, Any], extracted: dict[str, Any], revision_count: int) -> dict[str, Any]:
    """Check coverage and evidence, consulting supplemental material on retry."""
    policy = case["policy"]
    primary = case["primary_evidence"]
    supplement = case.get("supplemental_evidence") if revision_count > 0 else None
    return check_handoff({
        "type": "investigated",
        "covered": bool(policy["active"] and extracted["amount_usd"] <= policy["limit_usd"]),
        "invoice_present": bool(primary["invoice_present"] or (supplement and supplement["invoice_present"])),
        "receipt_present": bool(primary["receipt_present"] or (supplement and supplement["receipt_present"])),
        "used_supplemental": supplement is not None,
    })


def review(case: dict[str, Any], investigated: dict[str, Any], revision_count: int) -> dict[str, Any]:
    """Recommend a decision without performing routing or payment."""
    if not investigated["covered"]:
        recommendation, reason = "DENY", "Policy inactive or requested amount exceeds limit"
    elif not (investigated["invoice_present"] and investigated["receipt_present"]):
        if case.get("supplemental_evidence") and revision_count == 0:
            recommendation, reason = "RETURN", "Check supplemental evidence once"
        else:
            recommendation, reason = "NEEDS_INFO", "Invoice or receipt missing"
    else:
        recommendation, reason = "APPROVE", "Coverage and required evidence verified"
    return check_handoff({"type": "reviewed", "recommendation": recommendation, "reason": reason})
