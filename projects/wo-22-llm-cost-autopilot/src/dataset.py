"""Read SQuAD questions and paired answer traces from WO-20."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_DIR / "data" / "squad_v2_dev.json"
PREDICTIONS_PATH = PROJECT_DIR / "data" / "model_predictions.jsonl"


@dataclass(frozen=True)
class Example:
    """Question, context, gold answers, and paired historical outputs."""

    question_id: str
    title: str
    context: str
    question: str
    answers: tuple[str, ...]
    impossible: bool
    answer_a: str
    answer_b: str
    input_tokens_a: int
    output_tokens_a: int
    input_tokens_b: int
    output_tokens_b: int


def _read_predictions(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Index validated WO-20 prediction rows by question and prompt version."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}; copy WO-20 results/predictions.jsonl to this path"
        )
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            question_id = str(row["question_id"])
            version = str(row["prompt_version"])
            if version not in {"A", "B"} or version in indexed.get(question_id, {}):
                raise ValueError(f"Invalid or duplicate prediction at line {line_number}")
            indexed.setdefault(question_id, {})[version] = row
    if any(set(versions) != {"A", "B"} for versions in indexed.values()):
        raise ValueError("Every question needs exactly one A and one B prediction")
    return indexed


def load_examples(dataset_path: Path = DATA_PATH, predictions_path: Path = PREDICTIONS_PATH) -> list[Example]:
    """Load the pinned SQuAD split and pair it with WO-20 A/B answer traces."""
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Missing {dataset_path}; run `docker compose run --rm download`")
    predictions = _read_predictions(predictions_path)
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    examples: list[Example] = []
    for article in raw["data"]:
        title = str(article["title"])
        for paragraph in article["paragraphs"]:
            context = str(paragraph["context"])
            for question in paragraph["qas"]:
                qid = str(question["id"])
                pair = predictions.get(qid)
                if pair is None:
                    raise ValueError(f"Missing model predictions for {qid}")
                row_a, row_b = pair["A"], pair["B"]
                if row_a.get("model") != row_b.get("model"):
                    raise ValueError(f"A/B model mismatch for {qid}")
                answers = tuple(str(answer["text"]) for answer in question["answers"])
                impossible = bool(question["is_impossible"])
                if impossible != (not answers):
                    raise ValueError(f"Answerability mismatch for {qid}")
                examples.append(Example(
                    question_id=qid,
                    title=title,
                    context=context,
                    question=str(question["question"]),
                    answers=answers,
                    impossible=impossible,
                    answer_a=str(row_a["prediction"]),
                    answer_b=str(row_b["prediction"]),
                    input_tokens_a=int(row_a["prompt_tokens"]),
                    output_tokens_a=int(row_a["completion_tokens"]),
                    input_tokens_b=int(row_b["prompt_tokens"]),
                    output_tokens_b=int(row_b["completion_tokens"]),
                ))
    if len(examples) != len(predictions):
        raise ValueError("SQuAD and prediction question counts differ")
    return examples
