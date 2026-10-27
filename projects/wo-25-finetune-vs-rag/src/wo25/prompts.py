"""Prompt construction for the four compared application methods."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wo25.data import gsm_training_prompt

SYSTEM_PROMPT = (
    "You solve grade-school math word problems. Work carefully and show a concise "
    "calculation path. The final answer must end with #### followed by the number."
)
MMLU_SYSTEM_PROMPT = "Answer the multiple-choice question with one option letter only."


def build_gsm_messages(
    question: str,
    method: str,
    demonstrations: Sequence[dict[str, str]] = (),
) -> list[dict[str, str]]:
    """Build a consistent chat request, varying only included examples."""
    if method not in {"zero_shot", "few_shot", "rag", "lora"}:
        raise ValueError(f"Unknown method: {method}")
    content = gsm_training_prompt(question)
    if demonstrations:
        rendered = "\n\n".join(
            f"Example {index}:\nQuestion: {row['question']}\nSolution: {row['answer']}"
            for index, row in enumerate(demonstrations, start=1)
        )
        content = f"Use the worked examples as references, then solve the new problem.\n\n{rendered}\n\nNew problem:\nQuestion: {question}\nSolution:"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def build_mmlu_messages(
    question: dict[str, Any], demonstrations: Sequence[dict[str, Any]] = ()
) -> list[dict[str, str]]:
    """Build a subject-matched MMLU request with optional development examples."""
    content_parts: list[str] = []
    for example in demonstrations:
        content_parts.append(_render_mmlu_item(example, include_answer=True))
    content_parts.append(_render_mmlu_item(question, include_answer=False))
    return [
        {"role": "system", "content": MMLU_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]


def _render_mmlu_item(row: dict[str, Any], include_answer: bool) -> str:
    """Render one MMLU multiple-choice item and optionally its key."""
    labels = "ABCD"
    choices = "\n".join(
        f"{labels[index]}. {choice}" for index, choice in enumerate(row["choices"])
    )
    rendered = f"Question: {row['question']}\n{choices}"
    if include_answer:
        rendered += f"\nAnswer: {labels[int(row['answer'])]}"
    else:
        rendered += "\nAnswer:"
    return rendered

