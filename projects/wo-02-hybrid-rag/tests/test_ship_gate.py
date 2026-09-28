"""Regression checks for the measured WO-02 Ship Gate artifacts."""

import json
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIRECTORY = PROJECT_ROOT / "results"
EXPECTED_ANSWER_COUNT = 30


def _read_json(path: Path) -> object:
    """Read one committed result artifact as JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_hybrid_rerank_beats_bm25_ship_gate() -> None:
    """The measured final retrieval stage must improve both target metrics."""
    experiment = cast(
        dict[str, object], _read_json(RESULTS_DIRECTORY / "experiments.json")
    )
    retrieval = cast(dict[str, dict[str, float]], experiment["retrieval"])
    assert retrieval["hybrid_rerank"]["recall@10"] > retrieval["bm25"]["recall@10"]
    assert retrieval["hybrid_rerank"]["nDCG@10"] > retrieval["bm25"]["nDCG@10"]


def test_every_measured_answer_has_a_source_chunk() -> None:
    """All 30 generated answers must carry their recorded chunk citation."""
    answers = cast(
        list[dict[str, object]], _read_json(RESULTS_DIRECTORY / "answers.json")
    )
    assert len(answers) == EXPECTED_ANSWER_COUNT
    assert all(f"[{answer['citation']}]" in str(answer["answer"]) for answer in answers)


def test_failure_stages_are_reported_separately() -> None:
    """The committed analysis must retain independent stage-level counts."""
    analysis = cast(
        dict[str, object], _read_json(RESULTS_DIRECTORY / "failure_analysis.json")
    )
    assert int(analysis["retrieval_failure_count"]) > 0
    assert int(analysis["generation_failure_count"]) > 0
