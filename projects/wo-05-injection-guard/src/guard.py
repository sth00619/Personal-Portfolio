"""Enforce trust provenance, least privilege, output policy, and approval."""

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .models import Action, MockTools, safe_summary, score_profile
from .parser import proposed_actions, suspicious_sources

ALLOWED_TOOLS = {
    "evaluation": frozenset({"score", "publish"}),
    "finalize": frozenset({"email", "ats_write"}),
}
PRIVILEGED_TOOLS = frozenset({"email", "ats_write"})
UNTRUSTED_ORIGINS = frozenset({"body", "metadata", "tool_result", "metadata_score_hint"})
OUTPUT_RISK = re.compile(r"HIRE_ME_NOW|outside\.invalid|tool=", re.I)


@dataclass
class ConfirmationRegistry:
    """Hold one-use approvals issued through a separate trusted interface."""

    tickets: dict[str, tuple[str, str, str]] = field(default_factory=dict)

    def issue(self, action: Action, actor: str) -> str:
        """Bind one approval token to an exact action and a named actor."""
        if not actor.strip() or action.tool not in PRIVILEGED_TOOLS:
            raise ValueError("Privileged action and nonempty approver are required")
        token = uuid4().hex
        self.tickets[token] = (action.tool, repr(sorted(action.args.items())), actor)
        return token

    def valid(self, token: str | None, action: Action) -> bool:
        """Check that a ticket matches this exact action without consuming it."""
        if token is None or token not in self.tickets:
            return False
        tool, args, _actor = self.tickets[token]
        return tool == action.tool and args == repr(sorted(action.args.items()))

    def consume(self, token: str) -> None:
        """Remove a one-use approval immediately before the mock side effect."""
        self.tickets.pop(token)


class GuardedAgent:
    """Keep an intentionally gullible planner behind deterministic controls."""

    def __init__(self, registry: ConfirmationRegistry | None = None) -> None:
        """Create a router with its own separate confirmation registry."""
        self.registry = registry or ConfirmationRegistry()

    @staticmethod
    def _audit(
        case_id: str, family: str, stage: str, rule: str, action: Action | None, blocked: bool
    ) -> dict[str, Any]:
        """Create an audit event without copying sensitive source payloads."""
        return {
            "case_id": case_id,
            "family": family,
            "stage": stage,
            "rule": rule,
            "tool": action.tool if action else None,
            "source": action.origin if action else None,
            "blocked": blocked,
        }

    def route(
        self,
        action: Action,
        tools: MockTools,
        case_id: str,
        family: str,
        audit: list[dict[str, Any]],
        context: str = "evaluation",
        confirmation_token: str | None = None,
    ) -> bool:
        """Mediate every tool call, including proposals from untrusted text."""
        if context not in ALLOWED_TOOLS:
            raise ValueError(f"Unknown context: {context}")
        reasons: list[tuple[str, str]] = []
        if action.origin in UNTRUSTED_ORIGINS:
            reasons.append(("trust_boundary", "UNTRUSTED_INSTRUCTION"))
        if action.tool not in ALLOWED_TOOLS[context]:
            reasons.append(("tool_policy", "TOOL_NOT_ALLOWED"))
        if action.tool == "set_score" and action.origin in UNTRUSTED_ORIGINS:
            reasons.append(("tool_policy", "SCORE_SOURCE_UNTRUSTED"))
        if action.tool == "score":
            value = action.args.get("value")
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                reasons.append(("tool_policy", "INVALID_SCORE"))
        if action.tool == "publish" and OUTPUT_RISK.search(str(action.args.get("text", ""))):
            reasons.append(("output_scan", "OUTPUT_POLICY"))
        if action.tool in PRIVILEGED_TOOLS and not self.registry.valid(confirmation_token, action):
            reasons.append(("confirmation", "CONFIRMATION_REQUIRED"))
        for stage, rule in reasons:
            audit.append(self._audit(case_id, family, stage, rule, action, blocked=True))
        if reasons:
            return False
        if action.tool in PRIVILEGED_TOOLS and confirmation_token is not None:
            self.registry.consume(confirmation_token)
        tools.execute(action)
        return True

    def evaluate(self, record: dict[str, Any], legacy_hint_bug: bool = False) -> dict[str, Any]:
        """Score a resume, inspect lower-trust inputs, and block unsafe effects."""
        case_id = record["case_id"]
        family = record.get("family", "normal")
        tools = MockTools()
        audit: list[dict[str, Any]] = []
        for source in suspicious_sources(record):
            audit.append(self._audit(case_id, family, "input_classifier", "INPUT_SUSPECT", None, blocked=False))
        score = score_profile(record["resume_text"])
        self.route(Action("score", {"value": score}, "trusted_rubric"), tools, case_id, family, audit)
        self.route(
            Action("publish", {"text": safe_summary(case_id, score)}, "trusted_summary"),
            tools, case_id, family, audit,
        )
        for action in proposed_actions(record):
            if legacy_hint_bug and action.origin == "metadata_score_hint":
                # A deliberately vulnerable prior version trusted numeric PDF metadata.
                tools.execute(action)
                audit.append(self._audit(case_id, family, "legacy", "V1_HINT_ACCEPTED", action, blocked=False))
            else:
                self.route(action, tools, case_id, family, audit)
        return {
            "tools": tools,
            "audit": audit,
            "classifier_alert": any(event["rule"] == "INPUT_SUSPECT" for event in audit),
            "blocked_rules": sorted({event["rule"] for event in audit if event["blocked"]}),
        }
