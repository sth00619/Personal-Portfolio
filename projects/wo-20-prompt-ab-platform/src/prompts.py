"""Define the paired answer prompts and blinded judge rubric."""

from __future__ import annotations

from .dataset import QAExample


PROMPT_A_SYSTEM = (
    "Answer the question using only the supplied passage. Return a concise answer and no explanation."
)
PROMPT_B_SYSTEM = (
    "Answer the question using only the supplied passage. Return a concise answer and no explanation. "
    "If the passage does not contain enough information to answer, respond exactly: NO_ANSWER."
)
PROMPT_HASH_VERSION = "wo20-prompt-pair-v1"
ANSWER_PROMPTS = {"A": PROMPT_A_SYSTEM, "B": PROMPT_B_SYSTEM}


def answer_user_message(example: QAExample) -> str:
    """Build the identical question and context input shared by prompt A and B."""
    return f"Passage:\n{example.context}\n\nQuestion:\n{example.question}"


def judge_system_prompt() -> str:
    """Return a fixed 1–5 rubric for answer correctness and abstention."""
    return (
        "You are a blinded evaluator for extractive question answering. Score each candidate from 1 to 5. "
        "Use the passage and reference answers to judge factual correctness; for an unanswerable question, "
        "a clear abstention is correct and a fabricated answer is incorrect. Ignore style unless it changes meaning. "
        "Return only JSON with integer keys score_x and score_y, each from 1 to 5."
    )


def judge_user_message(
    example: QAExample,
    candidate_x: str,
    candidate_y: str,
) -> str:
    """Build a blinded pairwise rubric input without revealing prompt versions."""
    references = "\n".join(f"- {answer}" for answer in example.answers) or "- (unanswerable)"
    return (
        f"Passage:\n{example.context}\n\nQuestion:\n{example.question}\n\n"
        f"Reference answers:\n{references}\n\n"
        f"Candidate X:\n{candidate_x}\n\nCandidate Y:\n{candidate_y}"
    )
