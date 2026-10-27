"""Load, flatten, and optionally stratify the SQuAD 2.0 development split."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from datasets import load_dataset


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "squad_v2_dev.json"
DATASET_NAME = "SQuAD 2.0 dev"
SAMPLE_SEED = 20_071


@dataclass(frozen=True)
class QAExample:
    """One question, its supporting paragraph, and its reference answers."""

    question_id: str
    title: str
    context: str
    question: str
    answers: tuple[str, ...]
    is_impossible: bool


def load_examples(path: Path = DATA_PATH) -> list[QAExample]:
    """Read the verified local JSON through Hugging Face Datasets and flatten it."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}; run `docker compose run --rm download` first")
    articles = load_dataset(
        "json",
        data_files={"dev": str(path)},
        field="data",
        split="dev",
    )
    examples: list[QAExample] = []
    for article in articles:
        for paragraph in article["paragraphs"]:
            for question in paragraph["qas"]:
                raw_answers = question["answers"]
                if isinstance(raw_answers, dict):
                    answer_texts = raw_answers.get("text", [])
                elif isinstance(raw_answers, list):
                    answer_texts = [answer["text"] for answer in raw_answers]
                else:
                    raise ValueError("Unexpected SQuAD answer representation")
                examples.append(QAExample(
                    question_id=str(question["id"]),
                    title=str(article["title"]),
                    context=str(paragraph["context"]),
                    question=str(question["question"]),
                    answers=tuple(str(answer) for answer in answer_texts),
                    is_impossible=bool(question["is_impossible"]),
                ))
    if not examples or len({example.question_id for example in examples}) != len(examples):
        raise ValueError("SQuAD records are empty or question IDs are not unique")
    if any(example.is_impossible and example.answers for example in examples):
        raise ValueError("An unanswerable question unexpectedly has reference answers")
    if any(not example.is_impossible and not example.answers for example in examples):
        raise ValueError("An answerable question has no reference answer")
    return examples


def select_examples(
    examples: list[QAExample], limit: int, seed: int = SAMPLE_SEED
) -> list[QAExample]:
    """Return the full split or a deterministic answerable/unanswerable balance."""
    if limit <= 0 or limit >= len(examples):
        return examples
    if limit % 2:
        raise ValueError("A balanced sample size must be an even number")
    answerable = [item for item in examples if not item.is_impossible]
    unanswerable = [item for item in examples if item.is_impossible]
    half = limit // 2
    if min(len(answerable), len(unanswerable)) < half:
        raise ValueError("The requested balanced sample exceeds a segment's support")
    rng = np.random.default_rng(seed)
    chosen_answerable = rng.choice(len(answerable), size=half, replace=False)
    chosen_unanswerable = rng.choice(len(unanswerable), size=half, replace=False)
    selected = [answerable[int(index)] for index in chosen_answerable]
    selected.extend(unanswerable[int(index)] for index in chosen_unanswerable)
    return sorted(selected, key=lambda item: item.question_id)
