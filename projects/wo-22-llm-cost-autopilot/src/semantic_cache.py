"""Calibrate safe semantic reuse with WO-03's precision-gated threshold policy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer

from .dataset import Example
from .scoring import answer_f1


MIN_THRESHOLD = 0.70
MAX_THRESHOLD = 0.999
THRESHOLD_STEP = 0.001
TARGET_PRECISION = 0.995
MIN_VALIDATION_HITS = 50
SAFETY_MARGIN = 0.003


def variant(question: str) -> str:
    """Create a deterministic wording variation for a same-intent replay."""
    return f"Question: {question}"


def _canonical_question(question: str) -> str:
    """Normalize only case, punctuation, and whitespace for exact-cache precedence."""
    text = re.sub(r"[^\w\s]", " ", question.casefold())
    return " ".join(text.split())


@dataclass
class SemanticPolicy:
    """Character n-gram representation and selected cosine cutoff."""

    vectorizer: TfidfVectorizer
    threshold: float
    calibration: dict[str, float | int | bool]

    def similarity(self, first: str, second: str) -> float:
        """Return cosine similarity for a pair using the fitted local vectorizer."""
        matrix = self.vectorizer.transform([first, second])
        return float(matrix[0].multiply(matrix[1]).sum())


def _candidate_pairs(
    examples: list[Example],
) -> tuple[list[str], list[str], list[list[int]]]:
    """Create one safe rewrite and its same-context hard negatives per anchor."""
    groups: dict[tuple[str, str], list[Example]] = defaultdict(list)
    for item in examples:
        groups[(item.title, item.context)].append(item)
    positive_left: list[str] = []
    positive_right: list[str] = []
    negative_left: list[str] = []
    negative_right: list[str] = []
    negative_offsets: list[list[int]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        for item in group:
            positive_left.append(item.question)
            positive_right.append(variant(item.question))
            offsets: list[int] = []
            for other in group:
                if (
                    other.question_id != item.question_id
                    and _canonical_question(other.question) != _canonical_question(item.question)
                ):
                    offsets.append(len(negative_left))
                    negative_left.append(item.question)
                    negative_right.append(other.question)
            negative_offsets.append(offsets)
    all_left = positive_left + negative_left
    all_right = positive_right + negative_right
    return all_left, all_right, negative_offsets


def _threshold_rows(
    positive: NDArray[np.float64], hardest_negative: NDArray[np.float64]
) -> list[dict[str, float | int]]:
    """Score top-1 cache choices as safe hits, false hits, or misses per query."""
    thresholds = np.arange(MIN_THRESHOLD, MAX_THRESHOLD + THRESHOLD_STEP / 2, THRESHOLD_STEP)
    rows: list[dict[str, float | int]] = []
    for raw in thresholds:
        threshold = round(float(raw), 3)
        safe_hits = (positive >= threshold) & (positive > hardest_negative)
        false_hits_mask = (hardest_negative >= threshold) & (hardest_negative >= positive)
        true_hits = int(safe_hits.sum())
        false_hits = int(false_hits_mask.sum())
        hits = true_hits + false_hits
        rows.append({
            "threshold": threshold,
            "precision": true_hits / hits if hits else 1.0,
            "recall": true_hits / len(positive) if len(positive) else 0.0,
            "coverage": hits / len(positive) if len(positive) else 0.0,
            "true_hits": true_hits,
            "false_hits": false_hits,
        })
    return rows


def fit_semantic_policy(examples: list[Example]) -> SemanticPolicy:
    """Tune a conservative semantic match threshold on training articles only."""
    left, right, negative_offsets = _candidate_pairs(examples)
    if not negative_offsets:
        raise ValueError("No repeated-context question pairs are available for cache tuning")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), min_df=1, max_features=100_000,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(left + right)
    pair_count = len(left)
    similarities = np.asarray(
        matrix[:pair_count].multiply(matrix[pair_count:]).sum(axis=1)
    ).ravel()
    positive_count = len(negative_offsets)
    positives = similarities[:positive_count]
    hardest_negatives = np.asarray([
        max((similarities[positive_count + offset] for offset in offsets), default=0.0)
        for offsets in negative_offsets
    ], dtype=np.float64)
    curve = _threshold_rows(positives, hardest_negatives)
    candidates = [
        row for row in curve
        if float(row["precision"]) >= TARGET_PRECISION
        and int(row["true_hits"]) >= MIN_VALIDATION_HITS
    ]
    if candidates:
        selected = max(candidates, key=lambda row: (float(row["recall"]), float(row["coverage"])))
        threshold = min(MAX_THRESHOLD, round(float(selected["threshold"]) + SAFETY_MARGIN, 3))
        operating = next(row for row in curve if float(row["threshold"]) == threshold)
        calibration: dict[str, float | int | bool] = {
            "threshold_found": True,
            "pre_margin_threshold": float(selected["threshold"]),
            "pre_margin_precision": float(selected["precision"]),
            "selected_validation_precision": float(operating["precision"]),
            "selected_validation_recall": float(operating["recall"]),
            "selected_validation_safe_hits": int(operating["true_hits"]),
            "selected_validation_false_hits": int(operating["false_hits"]),
            "target_precision": TARGET_PRECISION,
            "safety_margin": SAFETY_MARGIN,
            "validation_query_count": positive_count,
        }
    else:
        threshold = 1.0
        calibration = {
            "threshold_found": False,
            "selected_validation_precision": 0.0,
            "selected_validation_recall": 0.0,
            "selected_validation_safe_hits": 0,
            "selected_validation_false_hits": 0,
            "target_precision": TARGET_PRECISION,
            "safety_margin": SAFETY_MARGIN,
            "validation_query_count": positive_count,
        }
    return SemanticPolicy(vectorizer, threshold, calibration)


def evaluate_replay(
    policy: SemanticPolicy, examples: list[Example], choices: list[str]
) -> dict[str, object]:
    """Score safe same-context replay hits and rejected semantic candidates."""
    if len(examples) != len(choices):
        raise ValueError("Every replay example must have its routed output")
    choice_by_id = {item.question_id: choice for item, choice in zip(examples, choices)}
    groups: dict[tuple[str, str], list[Example]] = defaultdict(list)
    for item in examples:
        groups[(item.title, item.context)].append(item)
    similarities: list[float] = []
    hit_count = 0
    safe_total = 0
    unsafe_total = 0
    false_hits = 0
    safe_hit_ids: list[str] = []
    false_hit_ids: list[str] = []
    cached_f1s: list[float] = []
    route_f1s: list[float] = []
    false_hit_cached_f1s: list[float] = []
    false_hit_route_f1s: list[float] = []
    for group in groups.values():
        for item in group:
            score = policy.similarity(item.question, variant(item.question))
            similarities.append(score)
            safe_total += 1
            negative_scores: list[tuple[float, Example]] = []
            for other in group:
                if (
                    other.question_id == item.question_id
                    or _canonical_question(other.question) == _canonical_question(item.question)
                ):
                    continue
                unsafe_total += 1
                negative_score = policy.similarity(item.question, other.question)
                negative_scores.append((negative_score, other))
            hardest_negative, nearest_negative = max(
                negative_scores, key=lambda candidate: candidate[0], default=(0.0, item)
            )
            route_prediction = item.answer_a if choice_by_id[item.question_id] == "A" else item.answer_b
            route_f1 = answer_f1(route_prediction, item.answers, item.impossible)
            route_f1s.append(route_f1)
            if score >= policy.threshold and score > hardest_negative:
                hit_count += 1
                safe_hit_ids.append(item.question_id)
                cached_f1s.append(route_f1)
            elif hardest_negative >= policy.threshold and hardest_negative >= score:
                false_hits += 1
                false_hit_ids.append(item.question_id)
                cached_choice = choice_by_id[nearest_negative.question_id]
                cached_prediction = nearest_negative.answer_a if cached_choice == "A" else nearest_negative.answer_b
                cached_f1 = answer_f1(cached_prediction, item.answers, item.impossible)
                false_hit_cached_f1s.append(cached_f1)
                false_hit_route_f1s.append(route_f1)
                cached_f1s.append(cached_f1)
            else:
                cached_f1s.append(route_f1)
    return {
        "safe_replay_pairs": safe_total,
        "safe_semantic_hits": hit_count,
        "safe_hit_rate": hit_count / safe_total if safe_total else 0.0,
        "unsafe_same_context_candidates": unsafe_total,
        "unsafe_cache_hits": false_hits,
        "unsafe_hit_rate": false_hits / unsafe_total if unsafe_total else 0.0,
        "heldout_top1_precision": hit_count / (hit_count + false_hits) if hit_count + false_hits else 1.0,
        "heldout_precision_gate_passed": (
            hit_count / (hit_count + false_hits) >= TARGET_PRECISION
            if hit_count + false_hits else False
        ),
        "mean_safe_similarity": float(np.mean(similarities)) if similarities else 0.0,
        "selected_threshold": policy.threshold,
        "route_quality_f1": float(np.mean(route_f1s)) if route_f1s else 0.0,
        "cache_quality_f1": float(np.mean(cached_f1s)) if cached_f1s else 0.0,
        "cache_quality_delta_f1": float(np.mean(cached_f1s) - np.mean(route_f1s)) if cached_f1s else 0.0,
        "false_hit_route_f1": float(np.mean(false_hit_route_f1s)) if false_hit_route_f1s else 0.0,
        "false_hit_reused_answer_f1": float(np.mean(false_hit_cached_f1s)) if false_hit_cached_f1s else 0.0,
        "_safe_hit_ids": safe_hit_ids,
        "_false_hit_ids": false_hit_ids,
    }
