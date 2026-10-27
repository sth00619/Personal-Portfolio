"""Deterministic exact-match extraction for GSM8K and MMLU."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

GSM_ANSWER_PATTERN = re.compile(r"####\s*\$?(-?\d[\d,]*(?:\.\d+)?)")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\$?(-?\d[\d,]*(?:\.\d+)?)(?![A-Za-z])")
MMLU_ANSWER_PATTERN = re.compile(r"(?im)^\s*(?:answer\s*:\s*)?\(?([A-D])\)?[.)]?\s*$")
MMLU_PREFIX_PATTERN = re.compile(
    r"(?im)^\s*(?:answer\s*(?:is|:)\s*|option\s+)?\(?([A-D])\)?(?=[.)\s]|$)"
)


def canonical_number(value: str) -> str | None:
    """Normalize comma-formatted integer or decimal text to a decimal string."""
    compact = value.replace(",", "").strip()
    try:
        number = Decimal(compact)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    normalized = number.normalize()
    return format(normalized, "f")


def parse_gsm8k_answer(text: str) -> str | None:
    """Extract the explicit final marker, falling back to the last number."""
    matches = GSM_ANSWER_PATTERN.findall(text)
    if matches:
        return canonical_number(matches[-1])
    numbers = NUMBER_PATTERN.findall(text)
    return canonical_number(numbers[-1]) if numbers else None


def parse_gold_gsm8k(answer: str) -> str | None:
    """Parse the official GSM8K final value after its #### marker."""
    matches = GSM_ANSWER_PATTERN.findall(answer)
    return canonical_number(matches[-1]) if matches else None


def parse_mmlu_answer(text: str) -> int | None:
    """Extract an A-D option index from a short or explanatory response."""
    strict_matches = MMLU_ANSWER_PATTERN.findall(text)
    if strict_matches:
        return ord(strict_matches[-1].upper()) - ord("A")
    prefix_matches = MMLU_PREFIX_PATTERN.findall(text)
    if prefix_matches:
        return ord(prefix_matches[-1].upper()) - ord("A")
    return None

