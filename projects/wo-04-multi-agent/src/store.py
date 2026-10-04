"""Redis snapshots with compare-and-swap and atomic idempotent payout."""

import json
from typing import Any

from redis import Redis

SAVE_LUA = """
local old = redis.call('GET', KEYS[1])
if not old then return -1 end
local state = cjson.decode(old)
if state.revision ~= tonumber(ARGV[1]) then return 0 end
redis.call('SET', KEYS[1], ARGV[2])
return 1
"""

PAYOUT_LUA = """
local old = redis.call('GET', KEYS[1])
if not old then return -1 end
local state = cjson.decode(old)
if state.revision ~= tonumber(ARGV[1]) then return 0 end
if redis.call('EXISTS', KEYS[2]) == 1 then return -2 end
redis.call('SET', KEYS[2], ARGV[3])
redis.call('SET', KEYS[1], ARGV[2])
return 1
"""


class RedisStore:
    """Store every node result outside the Python process."""

    def __init__(self, client: Redis, namespace: str) -> None:
        """Scope snapshots and payout records to one experiment run."""
        self.client = client
        self.namespace = namespace

    def state_key(self, case_id: str) -> str:
        """Return the Redis snapshot key for a case."""
        return f"wo04:{self.namespace}:state:{case_id}"

    def payout_key(self, case_id: str) -> str:
        """Return the unique payout key for a case."""
        return f"wo04:{self.namespace}:payout:{case_id}"

    def create(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create one initial snapshot without overwriting an earlier run."""
        key = self.state_key(state["case_id"])
        if not self.client.set(key, json.dumps(state, sort_keys=True), nx=True):
            raise ValueError(f"Case already exists: {state['case_id']}")
        return state

    def load(self, case_id: str) -> dict[str, Any]:
        """Reload a snapshot, including the next node and prior trace."""
        raw = self.client.get(self.state_key(case_id))
        if raw is None:
            raise KeyError(case_id)
        return json.loads(raw)

    def save(self, previous_revision: int, state: dict[str, Any]) -> None:
        """Atomically store a new revision or reject concurrent updates."""
        key = self.state_key(state["case_id"])
        result = self.client.eval(SAVE_LUA, 1, key, previous_revision, json.dumps(state, sort_keys=True))
        if result != 1:
            raise RuntimeError(f"Snapshot conflict or missing state: {result}")

    def commit_payout(self, previous_revision: int, state: dict[str, Any]) -> None:
        """Commit the synthetic payout and terminal snapshot in one Redis script."""
        case_id = state["case_id"]
        result = self.client.eval(
            PAYOUT_LUA,
            2,
            self.state_key(case_id),
            self.payout_key(case_id),
            previous_revision,
            json.dumps(state, sort_keys=True),
            json.dumps({"case_id": case_id, "amount_usd": state["extracted"]["amount_usd"]}),
        )
        if result != 1:
            raise RuntimeError(f"Payout already exists, conflict, or missing state: {result}")

    def payout_count(self, case_id: str) -> int:
        """Return one when a committed payout record exists."""
        return int(self.client.exists(self.payout_key(case_id)))
