"""Deterministic cost and latency model for replaying LLM requests."""

import hashlib
from dataclasses import dataclass

from .models import CachedAnswer, ReplayEvent

INPUT_PRICE_PER_MILLION = 1.25
OUTPUT_PRICE_PER_MILLION = 5.00
SYSTEM_PROMPT_TOKENS = 1_200
OUTPUT_TOKENS_BASE = 120
OUTPUT_TOKENS_VARIATION = 41
PREFIX_INPUT_DISCOUNT = 0.90
BASE_PREFILL_LATENCY_MS = 430.0
OUTPUT_TOKEN_LATENCY_MS = 6.2
LATENCY_JITTER_MS = 420.0
PREFIX_LATENCY_SAVING_MS = 260.0
EXACT_CACHE_LATENCY_MS = 3.0
SEMANTIC_CACHE_LATENCY_MS = 14.0
CACHE_JITTER_MS = 3.0


@dataclass(frozen=True)
class SimulationOutcome:
    """Baseline and actual cost-latency values for one request."""

    answer: CachedAnswer
    baseline_cost_usd: float
    actual_cost_usd: float
    baseline_latency_ms: float
    actual_latency_ms: float


def _fraction(value: str) -> float:
    """Map a stable hash to a deterministic fraction in the interval [0, 1)."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _token_counts(event: ReplayEvent) -> tuple[int, int]:
    """Estimate deterministic input and output token counts."""
    question_tokens = max(1, round(len(event.question.split()) * 1.35))
    output_tokens = OUTPUT_TOKENS_BASE + int(
        _fraction(f"tokens:{event.event_id}:{event.question}") * OUTPUT_TOKENS_VARIATION
    )
    return SYSTEM_PROMPT_TOKENS + question_tokens, output_tokens


def _generation_cost(input_tokens: int, output_tokens: int, prefix_hit: bool) -> float:
    """Calculate modeled API cost with an optional cached-prefix input discount."""
    charged_input = input_tokens * (1.0 - PREFIX_INPUT_DISCOUNT if prefix_hit else 1.0)
    return (
        charged_input * INPUT_PRICE_PER_MILLION
        + output_tokens * OUTPUT_PRICE_PER_MILLION
    ) / 1_000_000


def simulate_request(event: ReplayEvent, cache_level: str) -> SimulationOutcome:
    """Model uncached baseline and selected three-tier cache behavior."""
    input_tokens, output_tokens = _token_counts(event)
    jitter = _fraction(f"latency:{event.event_id}:{event.question}") * LATENCY_JITTER_MS
    baseline_latency = (
        BASE_PREFILL_LATENCY_MS + output_tokens * OUTPUT_TOKEN_LATENCY_MS + jitter
    )
    baseline_cost = _generation_cost(input_tokens, output_tokens, False)
    if cache_level == "exact":
        actual_latency = EXACT_CACHE_LATENCY_MS + jitter % CACHE_JITTER_MS
        actual_cost = 0.0
    elif cache_level == "semantic":
        actual_latency = SEMANTIC_CACHE_LATENCY_MS + jitter % CACHE_JITTER_MS
        actual_cost = 0.0
    else:
        prefix_hit = cache_level == "prefix"
        actual_latency = baseline_latency - (
            PREFIX_LATENCY_SAVING_MS if prefix_hit else 0.0
        )
        actual_cost = _generation_cost(input_tokens, output_tokens, prefix_hit)
    answer = CachedAnswer(
        answer=f"Simulated answer for {event.intent_id}", intent_id=event.intent_id
    )
    return SimulationOutcome(
        answer=answer,
        baseline_cost_usd=baseline_cost,
        actual_cost_usd=actual_cost,
        baseline_latency_ms=baseline_latency,
        actual_latency_ms=actual_latency,
    )
