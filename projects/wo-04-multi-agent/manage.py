"""Manually inspect, pause, resume, approve, or decline a synthetic claim."""

import argparse
import json
import os
from typing import Any

from redis import Redis

from run import load_cases
from src.engine import Engine
from src.store import RedisStore

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
MANUAL_NAMESPACE = "manual"


def summarize(state: dict[str, Any], payout_count: int) -> dict[str, Any]:
    """Return the state and trace fields needed for manual review."""
    return {
        "case_id": state["case_id"],
        "status": state["status"],
        "next_node": state["next_node"],
        "revision": state["revision"],
        "steps": state["step_count"],
        "tokens": state["token_count"],
        "modeled_cost_usd": state["cost_usd"],
        "reviewer_returns": state["revision_count"],
        "approval": state["approval"],
        "payout_count": payout_count,
        "trace": state["trace"],
    }


def main() -> None:
    """Run one manual workflow action in its own short-lived process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "resume", "approve", "decline"])
    parser.add_argument("case_id", help="Synthetic claim ID such as C001")
    parser.add_argument("--actor", help="Required approver identity for approve/decline")
    parser.add_argument("--events", type=int, help="Pause after this many additional node events")
    args = parser.parse_args()
    client = Redis.from_url(os.environ.get("REDIS_URL", DEFAULT_REDIS_URL), decode_responses=True)
    client.ping()
    store = RedisStore(client, MANUAL_NAMESPACE)
    engine = Engine(store)
    if args.action == "start":
        cases = {case["case_id"]: case for case in load_cases()}
        if args.case_id not in cases:
            parser.error("case_id is not in the synthetic fixture")
        engine.start(cases[args.case_id])
        state = engine.run(args.case_id, args.events)
    elif args.action == "resume":
        state = engine.run(args.case_id, args.events)
    elif args.action in {"approve", "decline"}:
        if not args.actor:
            parser.error("--actor is required for a human decision")
        engine.decide(args.case_id, args.action == "approve", args.actor)
        state = engine.run(args.case_id)
    else:
        state = store.load(args.case_id)
    print(json.dumps(summarize(state, store.payout_count(args.case_id)), indent=2))


if __name__ == "__main__":
    main()
