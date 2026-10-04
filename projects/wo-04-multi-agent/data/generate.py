"""Generate the committed, labeled synthetic insurance claim set."""

import json
from pathlib import Path
from typing import Any

CASE_COUNT = 30
PAID_COUNT = 10
DENIED_COUNT = 10
SECOND_PASS_COUNT = 5
LIMIT_USD = 1_000
DATA_PATH = Path(__file__).resolve().parent / "cases.json"


def build_cases() -> list[dict[str, Any]]:
    """Build 10 payable, 10 denied, and 10 incomplete synthetic cases."""
    cases: list[dict[str, Any]] = []
    for index in range(1, CASE_COUNT + 1):
        case_id = f"C{index:03d}"
        if index <= PAID_COUNT:
            amount = 100 + index * 25
            supplemental = index <= SECOND_PASS_COUNT
            primary = {"invoice_present": True, "receipt_present": not supplemental}
            policy = {"active": True, "limit_usd": LIMIT_USD}
            expected = "PAID"
        elif index <= PAID_COUNT + DENIED_COUNT:
            amount = 100 + index * 25
            supplemental = False
            primary = {"invoice_present": True, "receipt_present": True}
            policy = {"active": index % 2 == 0, "limit_usd": 200 if index % 2 == 0 else LIMIT_USD}
            expected = "DENIED"
        else:
            amount = 100 + index * 10
            supplemental = False
            primary = {"invoice_present": index % 2 == 0, "receipt_present": False}
            policy = {"active": True, "limit_usd": LIMIT_USD}
            expected = "NEEDS_INFO"
        cases.append({
            "case_id": case_id,
            "claim_document": f"Claim {case_id}: medical expense of ${amount}.",
            "policy": policy,
            "primary_evidence": primary,
            "supplemental_evidence": (
                {"invoice_present": True, "receipt_present": True} if supplemental else None
            ),
            "gold_terminal": expected,
            "synthetic": True,
        })
    return cases


def main() -> None:
    """Write a reproducible UTF-8 fixture without source documents or PII."""
    DATA_PATH.write_text(json.dumps(build_cases(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
