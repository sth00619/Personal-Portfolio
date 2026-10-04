"""Deliberately unprotected mock agent for controlled before/after comparison."""

from typing import Any

from .models import Action, MockTools, safe_summary, score_profile
from .parser import proposed_actions


def evaluate_unguarded(record: dict[str, Any]) -> MockTools:
    """Treat every lower-trust tool proposal as an executable instruction."""
    tools = MockTools()
    score = score_profile(record["resume_text"])
    tools.execute(Action("score", {"value": score}, "trusted_rubric"))
    tools.execute(Action("publish", {"text": safe_summary(record["case_id"], score)}, "trusted_summary"))
    for action in proposed_actions(record):
        tools.execute(action)
    return tools
