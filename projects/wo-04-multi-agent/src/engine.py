"""Bounded supervisor-led state machine with durable human approval."""

from copy import deepcopy
from typing import Any

from .contracts import check_handoff
from .store import RedisStore
from .workers import extract, investigate, review

MAX_STEPS = 16
MAX_TOKENS = 3_000
MAX_COST_USD = 0.005
INPUT_PRICE_PER_MILLION_USD = 1.0
OUTPUT_PRICE_PER_MILLION_USD = 4.0
NODE_TOKENS: dict[str, tuple[int, int]] = {
    "supervisor": (80, 30),
    "extractor": (150, 70),
    "investigator": (180, 80),
    "reviewer": (160, 70),
    "payout": (40, 15),
}
TERMINAL = {"PAID", "DENIED", "NEEDS_INFO", "DECLINED", "STEP_LIMIT", "TOKEN_LIMIT", "COST_LIMIT"}


def node_cost(node: str) -> float:
    """Price a deterministic token estimate for one node invocation."""
    input_tokens, output_tokens = NODE_TOKENS[node]
    return (input_tokens * INPUT_PRICE_PER_MILLION_USD + output_tokens * OUTPUT_PRICE_PER_MILLION_USD) / 1_000_000


class Engine:
    """Execute one node at a time and checkpoint every transition."""

    def __init__(
        self,
        store: RedisStore,
        max_steps: int = MAX_STEPS,
        max_tokens: int = MAX_TOKENS,
        max_cost_usd: float = MAX_COST_USD,
    ) -> None:
        """Set hard ceilings independently of worker recommendations."""
        self.store = store
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd

    def start(self, case: dict[str, Any]) -> dict[str, Any]:
        """Persist a new case before executing its first node."""
        state: dict[str, Any] = {
            "case_id": case["case_id"],
            "case": {key: value for key, value in case.items() if key != "gold_terminal"},
            "status": "RUNNING",
            "next_node": "supervisor",
            "phase": "start",
            "revision": 0,
            "step_count": 0,
            "token_count": 0,
            "cost_usd": 0.0,
            "revision_count": 0,
            "approval": None,
            "extracted": None,
            "investigated": None,
            "reviewed": None,
            "trace": [],
        }
        return self.store.create(state)

    def run(self, case_id: str, event_limit: int | None = None) -> dict[str, Any]:
        """Continue from Redis until terminal, human interrupt, or demo pause."""
        events = 0
        while True:
            state = self.store.load(case_id)
            if state["status"] != "RUNNING" or (event_limit is not None and events >= event_limit):
                return state
            self.step(case_id)
            events += 1

    def step(self, case_id: str) -> dict[str, Any]:
        """Execute one node and atomically checkpoint its result."""
        old = self.store.load(case_id)
        if old["status"] != "RUNNING":
            raise ValueError(f"Case is not runnable: {old['status']}")
        node = old["next_node"]
        state = deepcopy(old)
        input_tokens, output_tokens = NODE_TOKENS[node]
        proposed_cost = node_cost(node)
        reason = None
        if state["step_count"] + 1 > self.max_steps:
            reason = "STEP_LIMIT"
        elif state["token_count"] + input_tokens + output_tokens > self.max_tokens:
            reason = "TOKEN_LIMIT"
        elif state["cost_usd"] + proposed_cost > self.max_cost_usd + 1e-12:
            reason = "COST_LIMIT"
        if reason is not None:
            state["status"] = reason
            state["next_node"] = None
            self._record(state, "guard", reason, 0, 0, 0.0)
        else:
            self._execute(state, node)
            state["step_count"] += 1
            state["token_count"] += input_tokens + output_tokens
            state["cost_usd"] = round(state["cost_usd"] + proposed_cost, 8)
            self._record(state, node, state["phase"], input_tokens, output_tokens, proposed_cost)
        state["revision"] += 1
        if node == "payout" and reason is None:
            self.store.commit_payout(old["revision"], state)
        else:
            self.store.save(old["revision"], state)
        return state

    def decide(self, case_id: str, approve: bool, actor: str) -> dict[str, Any]:
        """Persist an explicit human decision before any payout can run."""
        if not actor.strip():
            raise ValueError("An approver identity is required")
        old = self.store.load(case_id)
        if old["status"] != "AWAITING_APPROVAL":
            raise ValueError(f"Approval unavailable in state {old['status']}")
        state = deepcopy(old)
        state["approval"] = {"approved": approve, "actor": actor}
        state["status"] = "RUNNING" if approve else "DECLINED"
        state["phase"] = "approved" if approve else "declined"
        state["next_node"] = "supervisor" if approve else None
        self._record(state, "human_approval", state["phase"], 0, 0, 0.0)
        state["revision"] += 1
        self.store.save(old["revision"], state)
        return state

    def _execute(self, state: dict[str, Any], node: str) -> None:
        """Run one specialist or supervisor transition without direct worker calls."""
        if node == "supervisor":
            self._route(state)
        elif node == "extractor":
            state["extracted"] = check_handoff(extract(state["case"]))
            state["phase"], state["next_node"] = "extracted", "supervisor"
        elif node == "investigator":
            state["investigated"] = check_handoff(investigate(
                state["case"], state["extracted"], state["revision_count"]
            ))
            state["phase"], state["next_node"] = "investigated", "supervisor"
        elif node == "reviewer":
            state["reviewed"] = check_handoff(review(
                state["case"], state["investigated"], state["revision_count"]
            ))
            state["phase"], state["next_node"] = "reviewed", "supervisor"
        elif node == "payout":
            if state["approval"] is None or not state["approval"]["approved"]:
                raise ValueError("Payout requires explicit recorded human approval")
            state["status"], state["phase"], state["next_node"] = "PAID", "paid", None
        else:
            raise ValueError(f"Unknown node: {node}")

    def _route(self, state: dict[str, Any]) -> None:
        """Make every routing and terminal-state decision centrally."""
        phase = state["phase"]
        if phase == "start":
            state["next_node"] = "extractor"
        elif phase == "extracted":
            state["next_node"] = "investigator"
        elif phase == "investigated":
            state["next_node"] = "reviewer"
        elif phase == "reviewed":
            recommendation = state["reviewed"]["recommendation"]
            if recommendation == "RETURN" and state["revision_count"] < 1:
                state["revision_count"] += 1
                state["next_node"] = "investigator"
            elif recommendation == "APPROVE":
                state["status"], state["next_node"] = "AWAITING_APPROVAL", None
            elif recommendation in {"DENY", "NEEDS_INFO"}:
                state["status"], state["next_node"] = (
                    "DENIED" if recommendation == "DENY" else "NEEDS_INFO"
                ), None
            else:
                state["status"], state["next_node"] = "NEEDS_INFO", None
        elif phase == "approved":
            if state["approval"] is None or not state["approval"]["approved"]:
                raise ValueError("No human approval recorded")
            state["next_node"] = "payout"
        else:
            raise ValueError(f"Unroutable phase: {phase}")

    @staticmethod
    def _record(
        state: dict[str, Any], node: str, outcome: str, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        """Append a deterministic trace event to the persisted snapshot."""
        state["trace"].append({
            "sequence": len(state["trace"]) + 1,
            "node": node,
            "outcome": outcome,
            "status": state["status"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 8),
        })
