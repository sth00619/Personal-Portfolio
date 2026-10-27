"""Entity-link metrics, paired document bootstrap, and error export."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import wilcoxon

from src.dataset import PairExample

BOOTSTRAP_REPETITIONS = 2000
RANDOM_SEED = 21021


def _counts(labels: np.ndarray, predictions: np.ndarray) -> tuple[int, int, int]:
    """Return true-positive, false-positive, and false-negative link counts."""
    true_positive = int(np.sum(labels & predictions))
    false_positive = int(np.sum(~labels & predictions))
    false_negative = int(np.sum(labels & ~predictions))
    return true_positive, false_positive, false_negative


def _f1(labels: np.ndarray, predictions: np.ndarray) -> float:
    """Compute micro F1 for exact question-answer entity links."""
    tp, fp, fn = _counts(labels, predictions)
    denominator = 2 * tp + fp + fn
    return (2 * tp / denominator) if denominator else 0.0


def _prf(labels: np.ndarray, predictions: np.ndarray) -> dict[str, float | int]:
    """Compute micro precision, recall, F1, and support for entity links."""
    tp, fp, fn = _counts(labels, predictions)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1_denominator = 2 * tp + fp + fn
    f1 = 2 * tp / f1_denominator if f1_denominator else 0.0
    return {
        "true_positive_links": tp,
        "false_positive_links": fp,
        "false_negative_links": fn,
        "gold_links": tp + fn,
        "predicted_links": tp + fp,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _document_f1(labels: np.ndarray, predictions: np.ndarray, docs: np.ndarray) -> dict[str, float]:
    """Compute a per-document F1 map, retaining zero-link forms as zero."""
    result: dict[str, float] = {}
    for document_id in np.unique(docs):
        mask = docs == document_id
        result[str(document_id)] = _f1(labels[mask], predictions[mask])
    return result


def paired_document_inference(
    labels: np.ndarray, prediction_a: np.ndarray, prediction_b: np.ndarray, docs: np.ndarray
) -> dict[str, Any]:
    """Estimate paired document-micro F1 delta and document bootstrap interval."""
    document_ids = np.unique(docs)
    grouped: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for document_id in document_ids:
        mask = docs == document_id
        grouped[str(document_id)] = (labels[mask], prediction_a[mask], prediction_b[mask])
    f1_a_by_doc = _document_f1(labels, prediction_a, docs)
    f1_b_by_doc = _document_f1(labels, prediction_b, docs)
    per_document_delta = np.asarray(
        [f1_b_by_doc[key] - f1_a_by_doc[key] for key in sorted(f1_a_by_doc)], dtype=float
    )
    rng = np.random.default_rng(RANDOM_SEED)
    deltas = np.empty(BOOTSTRAP_REPETITIONS, dtype=float)
    keys = sorted(grouped)
    for index in range(BOOTSTRAP_REPETITIONS):
        selected = rng.choice(keys, size=len(keys), replace=True)
        sampled_labels: list[np.ndarray] = []
        sampled_a: list[np.ndarray] = []
        sampled_b: list[np.ndarray] = []
        for key in selected:
            y, a, b = grouped[str(key)]
            sampled_labels.append(y)
            sampled_a.append(a)
            sampled_b.append(b)
        y = np.concatenate(sampled_labels)
        a = np.concatenate(sampled_a)
        b = np.concatenate(sampled_b)
        deltas[index] = _f1(y, b) - _f1(y, a)
    if np.allclose(per_document_delta, 0.0):
        p_value = 1.0
    else:
        p_value = float(wilcoxon(per_document_delta, alternative="two-sided", zero_method="wilcox").pvalue)
    return {
        "f1_delta_b_minus_a": _f1(labels, prediction_b) - _f1(labels, prediction_a),
        "paired_document_wilcoxon_p_value": p_value,
        "paired_document_bootstrap_95_ci": [float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))],
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "document_count": int(len(document_ids)),
    }


def build_report(
    examples: list[PairExample], text_predictions: np.ndarray, layout_predictions: np.ndarray
) -> dict[str, Any]:
    """Create metrics and test-split error summaries for the two link models."""
    labels = np.asarray([row.linked for row in examples], dtype=bool)
    docs = np.asarray([row.document_id for row in examples], dtype=str)
    return {
        "metadata": {
            "dataset": "FUNSD official test split",
            "training_split_documents": 149,
            "evaluation_split_documents": int(len(np.unique(docs))),
            "candidate_pairs": len(examples),
            "gold_links": int(labels.sum()),
            "positive_class_prevalence": float(labels.mean()),
            "task": "question-answer entity linking with gold entity candidates",
            "metric": "micro exact entity-link F1",
            "seed": RANDOM_SEED,
        },
        "text_only": _prf(labels, text_predictions),
        "text_plus_layout": _prf(labels, layout_predictions),
        "paired_layout_delta": paired_document_inference(labels, text_predictions, layout_predictions, docs),
    }


def save_error_cases(
    output_path: Path, examples: list[PairExample], text_predictions: np.ndarray, layout_predictions: np.ndarray
) -> Counter[str]:
    """Write detailed errors locally and return aggregate error transition counts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    with output_path.open("w", encoding="utf-8") as output:
        for row, text_pred, layout_pred in zip(examples, text_predictions, layout_predictions, strict=True):
            if bool(text_pred) == row.linked and bool(layout_pred) == row.linked:
                continue
            if bool(text_pred) != row.linked and bool(layout_pred) == row.linked:
                transition = "layout_fixed"
            elif bool(text_pred) == row.linked and bool(layout_pred) != row.linked:
                transition = "layout_regressed"
            elif not bool(text_pred) and not bool(layout_pred):
                transition = "both_missed"
            else:
                transition = "both_false_positive"
            counts[transition] += 1
            record = {
                "document_id": row.document_id,
                "question_id": row.question.entity_id,
                "answer_id": row.answer.entity_id,
                "question": row.question.text,
                "answer": row.answer.text,
                "gold_link": row.linked,
                "text_prediction": bool(text_pred),
                "layout_prediction": bool(layout_pred),
                "transition": transition,
                "question_box": row.question.box,
                "answer_box": row.answer.box,
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return counts
