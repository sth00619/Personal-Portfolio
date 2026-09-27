"""Regression gates for committed WO-03 measured artifacts."""

import json
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = PROJECT_ROOT / "results" / "experiment.json"
EXPECTED_QUERY_COUNT = 1_000
MAX_FALSE_HIT_RATE = 0.01


def _experiment() -> dict[str, object]:
    """Load the committed benchmark output."""
    return cast(dict[str, object], json.loads(RESULT_PATH.read_text(encoding="utf-8")))


def test_replay_meets_false_hit_ship_gate() -> None:
    """The 1,000-query run must remain below one percent semantic false hits."""
    replay = cast(dict[str, object], _experiment()["replay"])
    assert replay["queries"] == EXPECTED_QUERY_COUNT
    assert float(replay["semantic_false_hit_rate"]) < MAX_FALSE_HIT_RATE


def test_cache_reduces_cost_and_tail_latency() -> None:
    """The replay must demonstrate positive modeled cost and p95 reductions."""
    replay = cast(dict[str, object], _experiment()["replay"])
    assert float(replay["cost_reduction_rate"]) > 0.0
    assert float(replay["p95_reduction_rate"]) > 0.0


def test_prompt_change_busts_prior_response() -> None:
    """The saved demo must prove a new prompt version starts cold."""
    cache_bust = cast(dict[str, object], _experiment()["cache_bust"])
    assert cache_bust["second_v1_lookup"] == "exact"
    assert cache_bust["first_v2_lookup"] == "miss"
    assert cache_bust["prompt_change_busted_cache"] is True
