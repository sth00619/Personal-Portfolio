"""Separate document retrieval metrics from grounded-answer metrics."""

import re
from math import log2
from typing import TypeAlias

import numpy as np
from sentence_transformers import SentenceTransformer

from .models import GroundedAnswer, Qrels, Run

METRIC_CUTOFF = 10
MetricRow: TypeAlias = dict[str, float | int]
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def query_metrics(
    ranked_docs: list[str], relevant: dict[str, int], k: int = METRIC_CUTOFF
) -> dict[str, float]:
    """Compute document-level Recall@10, MRR, and graded nDCG@10."""
    if not relevant:
        raise ValueError("At least one relevant document is required")
    unique = list(dict.fromkeys(ranked_docs))
    top = unique[:k]
    recall = len(set(top) & relevant.keys()) / len(relevant)
    reciprocal_rank = next(
        (1.0 / rank for rank, doc_id in enumerate(unique, 1) if doc_id in relevant),
        0.0,
    )
    dcg = sum(
        (2 ** relevant.get(doc_id, 0) - 1) / log2(rank + 1)
        for rank, doc_id in enumerate(top, 1)
    )
    ideal = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum(
        (2**grade - 1) / log2(rank + 1)
        for rank, grade in enumerate(ideal, 1)
    )
    return {
        "recall@10": recall,
        "MRR": reciprocal_rank,
        "nDCG@10": dcg / idcg if idcg else 0.0,
    }


def evaluate_run(run: Run, qrels: Qrels) -> MetricRow:
    """Macro-average one retrieval run over all judged queries."""
    rows = [query_metrics(run.get(query_id, []), relevant) for query_id, relevant in qrels.items()]
    return {
        "n": len(rows),
        "recall@10": sum(row["recall@10"] for row in rows) / len(rows),
        "MRR": sum(row["MRR"] for row in rows) / len(rows),
        "nDCG@10": sum(row["nDCG@10"] for row in rows) / len(rows),
    }


def _normalized(text: str) -> str:
    """Normalize source and rationale text for exact extractive checking."""
    return " ".join(TOKEN_PATTERN.findall(text.lower()))


def evaluate_answers(
    answers: list[GroundedAnswer], embedding_model: SentenceTransformer
) -> dict[str, object]:
    """Measure citations, extractive faithfulness, relevance, and failure origin."""
    if not answers:
        raise ValueError("At least one grounded answer is required")
    citation_flags = [
        bool(answer.citation) and f"[{answer.citation}]" in answer.answer
        for answer in answers
    ]
    extractive_flags = [
        _normalized(answer.rationale) in _normalized(answer.citation_text)
        for answer in answers
    ]
    citation_correctness_flags = [
        answer.citation.split("#", maxsplit=1)[0] in answer.relevant_doc_ids
        for answer in answers
    ]
    verdict_flags = [
        answer.predicted_label == answer.expected_label for answer in answers
    ]
    faithfulness_flags = [
        extractive and citation_correct and verdict_correct
        for extractive, citation_correct, verdict_correct in zip(
            extractive_flags, citation_correctness_flags, verdict_flags
        )
    ]
    question_texts = [
        f"Does evidence support or contradict this claim? {answer.claim}"
        for answer in answers
    ]
    answer_texts = [answer.answer for answer in answers]
    vectors = embedding_model.encode(
        question_texts + answer_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    midpoint = len(answers)
    relevance = np.sum(vectors[:midpoint] * vectors[midpoint:], axis=1)

    retrieval_failures = 0
    generation_failures = 0
    successes = 0
    by_type: dict[str, dict[str, int]] = {}
    for answer, faithful, correct in zip(
        answers, faithfulness_flags, verdict_flags
    ):
        retrieved = bool(set(answer.relevant_doc_ids) & set(answer.retrieved_doc_ids[:10]))
        bucket = by_type.setdefault(
            answer.question_type,
            {"n": 0, "retrieval_failure": 0, "generation_failure": 0, "success": 0},
        )
        bucket["n"] += 1
        if not retrieved:
            retrieval_failures += 1
            bucket["retrieval_failure"] += 1
        elif not faithful or not correct:
            generation_failures += 1
            bucket["generation_failure"] += 1
        else:
            successes += 1
            bucket["success"] += 1

    count = len(answers)
    return {
        "n": count,
        "citation_coverage": sum(citation_flags) / count,
        "citation_correctness": sum(citation_correctness_flags) / count,
        "extractive_grounding": sum(extractive_flags) / count,
        "faithfulness": sum(faithfulness_flags) / count,
        "answer_relevance_cosine": float(np.mean(relevance)),
        "verdict_accuracy": sum(verdict_flags) / count,
        "retrieval_failures": retrieval_failures,
        "generation_failures": generation_failures,
        "successes": successes,
        "by_type": by_type,
    }
