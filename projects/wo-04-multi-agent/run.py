"""Replay 30 labeled claims and save reproducible Ship Gate evidence."""

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from redis import Redis

from src.engine import MAX_COST_USD, Engine
from src.report import write_results
from src.store import RedisStore

PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "cases.json"
OUTPUT_DIR = PROJECT_DIR / "results"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def load_cases(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load the synthetic, labeled input set."""
    return json.loads(path.read_text(encoding="utf-8"))


def replay(client: Redis, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run all cases, applying clearly scripted approvals to payable claims."""
    store = RedisStore(client, f"replay-{uuid4().hex}")
    engine = Engine(store)
    rows: list[dict[str, Any]] = []
    for case in cases:
        engine.start(case)
        state = engine.run(case["case_id"])
        if state["status"] == "AWAITING_APPROVAL":
            state = engine.decide(case["case_id"], True, actor="synthetic-evaluation-approver")
            state = engine.run(case["case_id"])
        rows.append({
            "case_id": case["case_id"],
            "gold_terminal": case["gold_terminal"],
            "terminal": state["status"],
            "steps": state["step_count"],
            "tokens": state["token_count"],
            "cost_usd": state["cost_usd"],
            "reviewer_returns": state["revision_count"],
            "path": [event["node"] for event in state["trace"]],
            "trace": state["trace"],
            "approval": state["approval"],
            "payout_count": store.payout_count(case["case_id"]),
        })
    demo_case = cases[0]
    demo_store = RedisStore(client, f"resume-{uuid4().hex}")
    demo_engine = Engine(demo_store)
    demo_engine.start(demo_case)
    paused = demo_engine.run(demo_case["case_id"], event_limit=3)
    restarted_engine = Engine(demo_store)
    resumed = restarted_engine.run(demo_case["case_id"])
    if resumed["status"] == "AWAITING_APPROVAL":
        restarted_engine.decide(demo_case["case_id"], True, "synthetic-evaluation-approver")
        resumed = restarted_engine.run(demo_case["case_id"])
    normal = rows[0]
    result = {
        "dataset": "30 entirely synthetic insurance claims",
        "worker_boundary": "Deterministic rules with fixed estimated tokens; no LLM API calls",
        "storage_boundary": "Redis snapshots and payout records executed",
        "cases": rows,
        "correct_count": sum(item["terminal"] == item["gold_terminal"] for item in rows),
        "reviewer_return_count": sum(item["reviewer_returns"] for item in rows),
        "approval_count": sum(item["approval"] is not None for item in rows),
        "payout_count": sum(item["payout_count"] for item in rows),
        "max_cost_usd": max(item["cost_usd"] for item in rows),
        "cost_cap_usd": MAX_COST_USD,
        "resume_demo": {
            "paused_after_events": len(paused["trace"]),
            "paused_next_node": paused["next_node"],
            "terminal": resumed["status"],
            "same_terminal": resumed["status"] == normal["terminal"],
            "same_trace_path": [event["node"] for event in resumed["trace"]] == normal["path"],
            "payout_count": demo_store.payout_count(demo_case["case_id"]),
        },
    }
    return result


def main() -> None:
    """Connect to Redis, run the replay, and persist charts and traces."""
    client = Redis.from_url(os.environ.get("REDIS_URL", DEFAULT_REDIS_URL), decode_responses=True)
    client.ping()
    results = replay(client, load_cases())
    write_results(OUTPUT_DIR, results)
    print(json.dumps({key: value for key, value in results.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
