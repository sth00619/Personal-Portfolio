"""Real Redis checks of approval, replay, resume, bounds, and retry."""

from copy import deepcopy

import pytest

from run import load_cases, replay
from src.engine import MAX_COST_USD, MAX_STEPS, MAX_TOKENS, Engine
from src.store import RedisStore

CASES = load_cases()


def test_all_30_cases_have_traces_and_correct_terminal(store: RedisStore) -> None:
    """Exercise every labeled path, including five reviewer returns."""
    result = replay(store.client, CASES)
    assert len(result["cases"]) == 30
    assert result["correct_count"] == 30
    assert result["reviewer_return_count"] == 5
    assert result["approval_count"] == 10
    assert result["payout_count"] == 10
    assert all(row["trace"] and row["cost_usd"] <= MAX_COST_USD for row in result["cases"])
    assert all(row["steps"] <= MAX_STEPS and row["tokens"] <= MAX_TOKENS for row in result["cases"])
    assert result["resume_demo"]["same_terminal"] is True
    assert result["resume_demo"]["same_trace_path"] is True


def test_approval_interrupt_precedes_atomic_payout(store: RedisStore) -> None:
    """Require a human identity, then commit only one payout record."""
    engine = Engine(store)
    engine.start(CASES[5])
    paused = engine.run(CASES[5]["case_id"])
    assert paused["status"] == "AWAITING_APPROVAL"
    assert store.payout_count(CASES[5]["case_id"]) == 0
    with pytest.raises(ValueError):
        engine.step(CASES[5]["case_id"])
    with pytest.raises(ValueError):
        engine.decide(CASES[5]["case_id"], True, actor=" ")
    engine.decide(CASES[5]["case_id"], True, actor="test-human")
    completed = engine.run(CASES[5]["case_id"])
    assert completed["status"] == "PAID"
    assert store.payout_count(CASES[5]["case_id"]) == 1
    assert engine.run(CASES[5]["case_id"])["status"] == "PAID"
    assert store.payout_count(CASES[5]["case_id"]) == 1
    assert [item["node"] for item in completed["trace"]][-3:] == [
        "human_approval", "supervisor", "payout"
    ]


def test_decline_never_pays(store: RedisStore) -> None:
    """A rejected human decision is terminal without a payout side effect."""
    engine = Engine(store)
    engine.start(CASES[6])
    assert engine.run(CASES[6]["case_id"])["status"] == "AWAITING_APPROVAL"
    engine.decide(CASES[6]["case_id"], False, actor="test-human")
    assert engine.run(CASES[6]["case_id"])["status"] == "DECLINED"
    assert store.payout_count(CASES[6]["case_id"]) == 0


def test_snapshot_resume_matches_uninterrupted_path(store: RedisStore) -> None:
    """A new engine instance resumes a reviewer-return case from Redis."""
    engine = Engine(store)
    engine.start(CASES[0])
    paused = engine.run(CASES[0]["case_id"], event_limit=6)
    assert paused["status"] == "RUNNING"
    assert paused["revision"] == 6
    restarted = Engine(store)
    assert restarted.run(CASES[0]["case_id"])["status"] == "AWAITING_APPROVAL"
    restarted.decide(CASES[0]["case_id"], True, actor="test-human")
    resumed = restarted.run(CASES[0]["case_id"])
    assert resumed["status"] == "PAID"
    assert resumed["revision_count"] == 1
    assert sum(event["node"] == "reviewer" for event in resumed["trace"]) == 2
    assert store.payout_count(CASES[0]["case_id"]) == 1


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        ({"max_steps": 1}, "STEP_LIMIT"),
        ({"max_tokens": 100}, "TOKEN_LIMIT"),
        ({"max_cost_usd": 0.00001}, "COST_LIMIT"),
    ],
)
def test_hard_guards_stop_before_exceeding_limit(
    store: RedisStore, limits: dict[str, int | float], expected: str
) -> None:
    """Enforce budget and step ceilings in code before invoking a node."""
    case = deepcopy(CASES[0])
    engine = Engine(store, **limits)
    engine.start(case)
    state = engine.run(case["case_id"])
    assert state["status"] == expected
    assert state["step_count"] <= engine.max_steps
    assert state["token_count"] <= engine.max_tokens
    assert state["cost_usd"] <= engine.max_cost_usd
    assert state["trace"][-1]["node"] == "guard"
    assert store.payout_count(case["case_id"]) == 0


def test_stale_snapshot_cannot_overwrite_terminal_state(store: RedisStore) -> None:
    """Compare-and-swap rejects a stale writer after a transition."""
    engine = Engine(store)
    old = engine.start(CASES[10])
    assert "gold_terminal" not in old["case"]
    engine.step(CASES[10]["case_id"])
    with pytest.raises(RuntimeError):
        store.save(old["revision"], old)
