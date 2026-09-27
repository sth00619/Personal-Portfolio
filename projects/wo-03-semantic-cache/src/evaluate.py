"""Threshold tuning and replay-metric aggregation."""

from collections import Counter
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from .models import ReplayRecord

MIN_THRESHOLD = 0.70
MAX_THRESHOLD = 0.999
THRESHOLD_STEP = 0.001
TARGET_PRECISION = 0.995
MIN_VALIDATION_TRUE_HITS = 50
THRESHOLD_SAFETY_MARGIN = 0.003


def threshold_curve(
    similarities: NDArray[np.float32], labels: NDArray[np.bool_]
) -> list[dict[str, float | int]]:
    """Measure precision, recall, false-hit rate, and coverage across thresholds."""
    thresholds = np.arange(
        MIN_THRESHOLD, MAX_THRESHOLD + THRESHOLD_STEP / 2, THRESHOLD_STEP
    )
    rows: list[dict[str, float | int]] = []
    positives = int(np.sum(labels))
    for raw_threshold in thresholds:
        threshold = round(float(raw_threshold), 3)
        predicted = similarities >= threshold
        true_hits = int(np.sum(predicted & labels))
        false_hits = int(np.sum(predicted & ~labels))
        hit_count = true_hits + false_hits
        precision = true_hits / hit_count if hit_count else 1.0
        recall = true_hits / positives if positives else 0.0
        rows.append(
            {
                "threshold": threshold,
                "precision": precision,
                "recall": recall,
                "false_hit_rate": false_hits / hit_count if hit_count else 0.0,
                "coverage": hit_count / len(labels),
                "true_hits": true_hits,
                "false_hits": false_hits,
            }
        )
    return rows


def select_threshold(curve: Sequence[dict[str, float | int]]) -> float:
    """Choose the highest-recall threshold meeting the conservative precision gate."""
    candidates = [
        row
        for row in curve
        if float(row["precision"]) >= TARGET_PRECISION
        and int(row["true_hits"]) >= MIN_VALIDATION_TRUE_HITS
    ]
    if not candidates:
        raise ValueError("No threshold meets the validation precision policy")
    selected = max(
        candidates,
        key=lambda row: (
            float(row["recall"]),
            float(row["coverage"]),
            -float(row["threshold"]),
        ),
    )
    conservative_threshold = min(
        MAX_THRESHOLD,
        round(float(selected["threshold"]) + THRESHOLD_SAFETY_MARGIN, 3),
    )
    return min(
        (float(row["threshold"]) for row in curve),
        key=lambda threshold: abs(threshold - conservative_threshold),
    )


def summarize_replay(records: list[ReplayRecord]) -> dict[str, object]:
    """Aggregate hit quality, modeled cost, and latency percentiles."""
    if not records:
        raise ValueError("At least one replay record is required")
    levels = Counter(record.cache_level for record in records)
    semantic_hits = [record for record in records if record.cache_level == "semantic"]
    false_semantic_hits = sum(record.valid_hit is False for record in semantic_hits)
    response_hits = levels["exact"] + levels["semantic"]
    cache_assists = response_hits + levels["prefix"]
    baseline_cost = sum(record.baseline_cost_usd for record in records)
    actual_cost = sum(record.actual_cost_usd for record in records)
    baseline_latency = np.asarray(
        [record.baseline_latency_ms for record in records], dtype=np.float64
    )
    actual_latency = np.asarray(
        [record.actual_latency_ms for record in records], dtype=np.float64
    )
    count = len(records)
    return {
        "queries": count,
        "hit_counts": dict(sorted(levels.items())),
        "response_hit_rate": response_hits / count,
        "cache_assist_rate": cache_assists / count,
        "semantic_hits": len(semantic_hits),
        "semantic_false_hits": false_semantic_hits,
        "semantic_false_hit_rate": (
            false_semantic_hits / len(semantic_hits) if semantic_hits else 0.0
        ),
        "semantic_precision": (
            1.0 - false_semantic_hits / len(semantic_hits) if semantic_hits else 1.0
        ),
        "baseline_cost_usd": baseline_cost,
        "actual_cost_usd": actual_cost,
        "cost_saved_usd": baseline_cost - actual_cost,
        "cost_reduction_rate": (baseline_cost - actual_cost) / baseline_cost,
        "baseline_p50_ms": float(np.percentile(baseline_latency, 50)),
        "actual_p50_ms": float(np.percentile(actual_latency, 50)),
        "p50_reduction_rate": 1.0
        - float(np.percentile(actual_latency, 50))
        / float(np.percentile(baseline_latency, 50)),
        "baseline_p95_ms": float(np.percentile(baseline_latency, 95)),
        "actual_p95_ms": float(np.percentile(actual_latency, 95)),
        "p95_reduction_rate": 1.0
        - float(np.percentile(actual_latency, 95))
        / float(np.percentile(baseline_latency, 95)),
    }
