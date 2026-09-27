"""Tests for semantic-threshold selection and replay quality metrics."""

from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluate import select_threshold, summarize_replay, threshold_curve
from src.models import ReplayRecord


def _record(level: str, valid: bool | None) -> ReplayRecord:
    """Build a compact deterministic replay record."""
    return ReplayRecord(
        event_id=0,
        pair_id=0,
        request_kind="test",
        cache_level=level,
        valid_hit=valid,
        similarity=0.95 if level == "semantic" else None,
        baseline_cost_usd=1.0,
        actual_cost_usd=0.0 if level in {"exact", "semantic"} else 0.5,
        baseline_latency_ms=100.0,
        actual_latency_ms=5.0 if level in {"exact", "semantic"} else 80.0,
    )


def test_replay_summary_counts_false_semantic_hits_only() -> None:
    """False-hit rate should use semantic response hits as its denominator."""
    summary = summarize_replay(
        [_record("exact", True), _record("semantic", True), _record("semantic", False), _record("prefix", None)]
    )
    assert summary["response_hit_rate"] == 0.75
    assert summary["semantic_false_hit_rate"] == 0.5
    assert summary["cache_assist_rate"] == 1.0


def test_threshold_policy_prefers_recall_after_precision_gate() -> None:
    """Selection should choose the most recall among rows meeting the policy."""
    similarities = np.asarray([0.99] * 60 + [0.90] * 60, dtype=np.float32)
    labels = np.asarray([True] * 60 + [False] * 60, dtype=np.bool_)
    curve = threshold_curve(similarities, labels)
    assert select_threshold(curve) == 0.904
