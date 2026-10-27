"""Reuse the price rules recorded by WO-18 and WO-20."""

from __future__ import annotations

from dataclasses import dataclass


MICRO_USD_PER_USD = 1_000_000
WO20_MODEL = "gpt-6-luna"
WO20_INPUT_USD_PER_MILLION = 0.10
WO20_OUTPUT_USD_PER_MILLION = 0.50
WO18_INPUT_MICRO_USD_PER_TOKEN = 2.0
WO18_OUTPUT_MICRO_USD_PER_TOKEN = 8.0


@dataclass(frozen=True)
class PriceProfile:
    """A price tier copied from an existing portfolio measurement."""

    name: str
    source: str
    input_usd_per_million: float
    output_usd_per_million: float


LOW_COST_PROFILE = PriceProfile(
    "economy", "WO-20 GPT-6 Luna rate", WO20_INPUT_USD_PER_MILLION,
    WO20_OUTPUT_USD_PER_MILLION,
)
HIGH_COST_PROFILE = PriceProfile(
    "premium", "WO-18 synthetic provider rate",
    WO18_INPUT_MICRO_USD_PER_TOKEN,
    WO18_OUTPUT_MICRO_USD_PER_TOKEN,
)


def request_cost_usd(input_tokens: int, output_tokens: int, profile: PriceProfile) -> float:
    """Compute a request cost from an existing per-million-token rate."""
    return (
        input_tokens * profile.input_usd_per_million
        + output_tokens * profile.output_usd_per_million
    ) / MICRO_USD_PER_USD
