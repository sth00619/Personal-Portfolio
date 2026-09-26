"""Tests for retrieval-versus-generation failure classification."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyze import build_failure_analysis
from src.models import GroundedAnswer


def test_failure_analysis_keeps_pipeline_stages_separate() -> None:
    """A missed document and a wrong verdict must appear in different buckets."""
    queries = {"r": "retrieval miss", "g": "generation miss"}
    qrels = {"r": {"gold-r": 1}, "g": {"gold-g": 1}}
    run = {"r": ["wrong"], "g": ["gold-g"]}
    answer = GroundedAnswer(
        query_id="g",
        question_type="lookup",
        expected_label="SUPPORT",
        predicted_label="CONTRADICT",
        claim="generation miss",
        answer="CONTRADICT. Evidence. [gold-g#c0]",
        rationale="Evidence.",
        citation="gold-g#c0",
        citation_text="Evidence.",
        confidence=0.9,
        relevant_doc_ids=("gold-g",),
        retrieved_doc_ids=("gold-g",),
        relevant_rank=1,
    )
    analysis = build_failure_analysis(queries, qrels, run, [answer])
    assert analysis["retrieval_failure_count"] == 1
    assert analysis["generation_failure_count"] == 1
