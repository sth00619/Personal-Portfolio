"""Load SciFact and the balanced 30-question generation set."""

import csv
import json
from pathlib import Path
from typing import cast

from .models import Corpus, EvalQuestion, Qrels, Queries

QUESTION_TEMPLATE = (
    "Does the cited scientific evidence SUPPORT or CONTRADICT this claim? "
    "Claim: {claim}"
)
ALLOWED_LABELS = {"SUPPORT", "CONTRADICT"}
ALLOWED_QUESTION_TYPES = {"lookup", "comparison", "calculation"}
EXPECTED_QUESTION_COUNT = 30


def _load_jsonl(path: Path) -> dict[str, dict[str, object]]:
    """Load JSON Lines objects keyed by their ``_id`` field."""
    rows: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = cast(dict[str, object], json.loads(line))
            rows[str(row["_id"])] = row
    return rows


def load_scifact(folder: Path) -> tuple[Corpus, Queries, Qrels]:
    """Load the corpus and the 300 queries judged in SciFact's test qrels."""
    corpus = _load_jsonl(folder / "corpus.jsonl")
    raw_queries = _load_jsonl(folder / "queries.jsonl")
    qrels: Qrels = {}
    with (folder / "qrels" / "test.tsv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            score = int(row["score"])
            if score > 0:
                qrels.setdefault(row["query-id"], {})[row["corpus-id"]] = score
    queries = {qid: str(raw_queries[qid]["text"]) for qid in qrels}
    if len(queries) != 300:
        raise ValueError(f"Expected 300 judged SciFact queries, found {len(queries)}")
    return corpus, queries, qrels


def _evidence_labels(metadata: object) -> set[str]:
    """Collect evidence labels from one SciFact query metadata object."""
    labels: set[str] = set()
    if not isinstance(metadata, dict):
        return labels
    for evidence_groups in metadata.values():
        if not isinstance(evidence_groups, list):
            continue
        for evidence in evidence_groups:
            if isinstance(evidence, dict) and "label" in evidence:
                labels.add(str(evidence["label"]))
    return labels


def load_eval_questions(dataset_folder: Path, selection_path: Path) -> list[EvalQuestion]:
    """Build 30 deterministic questions from selected human-labeled claims."""
    raw_queries = _load_jsonl(dataset_folder / "queries.jsonl")
    _, _, qrels = load_scifact(dataset_folder)
    selections = cast(list[dict[str, str]], json.loads(selection_path.read_text(encoding="utf-8")))
    if len(selections) != EXPECTED_QUESTION_COUNT:
        raise ValueError(f"Expected {EXPECTED_QUESTION_COUNT} question selections")

    questions: list[EvalQuestion] = []
    for selection in selections:
        qid = selection["query_id"]
        question_type = selection["type"]
        if question_type not in ALLOWED_QUESTION_TYPES:
            raise ValueError(f"Unsupported question type: {question_type}")
        row = raw_queries[qid]
        labels = _evidence_labels(row.get("metadata"))
        if len(labels) != 1 or not labels <= ALLOWED_LABELS:
            raise ValueError(f"Query {qid} does not have one usable human label")
        claim = str(row["text"])
        questions.append(
            EvalQuestion(
                query_id=qid,
                question_type=question_type,
                question=QUESTION_TEMPLATE.format(claim=claim),
                claim=claim,
                expected_label=next(iter(labels)),
                relevant_doc_ids=tuple(qrels[qid]),
            )
        )

    counts = {kind: sum(q.question_type == kind for q in questions) for kind in ALLOWED_QUESTION_TYPES}
    if set(counts.values()) != {10}:
        raise ValueError(f"Question types must be balanced 10/10/10: {counts}")
    return questions
