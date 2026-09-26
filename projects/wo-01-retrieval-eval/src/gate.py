"""Recall regression gate shared by CI and unit tests."""

from typing import TypedDict

MAX_RECALL_DROP = 0.01


class GateResult(TypedDict):
    """Minimal shape consumed from baseline and candidate result files."""

    config: dict[str, object]
    summary: dict[str, dict[str, float | int]]


def assert_recall_within_tolerance(
    baseline: GateResult,
    candidate: GateResult,
    tolerance: float = MAX_RECALL_DROP,
) -> None:
    """Raise when a comparable candidate loses more recall than allowed."""
    if candidate["config"] != baseline["config"]:
        raise AssertionError("Candidate configuration differs from the baseline")
    baseline_count = baseline["summary"]["all"]["n"]
    candidate_count = candidate["summary"]["all"]["n"]
    if candidate_count != baseline_count:
        raise AssertionError(
            f"Judged query count differs: {candidate_count} != {baseline_count}"
        )
    actual = float(candidate["summary"]["all"]["recall@10"])
    expected = float(baseline["summary"]["all"]["recall@10"])
    minimum = expected - tolerance
    if actual < minimum:
        raise AssertionError(
            f"Recall@10 regression: {actual:.4f} < {minimum:.4f} "
            f"(baseline {expected:.4f} minus {tolerance:.2%})"
        )
