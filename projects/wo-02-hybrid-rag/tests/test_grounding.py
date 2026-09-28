"""Tests for citation faithfulness and failure-source separation."""

from pathlib import Path
import sys

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluate import evaluate_answers
from src.generate import evidence_sentences
from src.models import GroundedAnswer


class FakeEmbeddingModel:
    """Return fixed normalized vectors for deterministic relevance tests."""

    def encode(self, texts: list[str], **_kwargs: object) -> NDArray[np.float32]:
        """Encode every input as the same unit vector."""
        return np.asarray([[1.0, 0.0] for _text in texts], dtype=np.float32)


def _answer(
    query_id: str,
    expected: str,
    predicted: str,
    relevant_doc: str,
    retrieved_docs: tuple[str, ...],
) -> GroundedAnswer:
    """Build one cited extractive answer for aggregate metric tests."""
    rationale = "The source sentence is quoted exactly."
    citation = f"{retrieved_docs[0]}#c0"
    return GroundedAnswer(
        query_id=query_id,
        question_type="lookup",
        expected_label=expected,
        predicted_label=predicted,
        claim="A test claim.",
        answer=f"{predicted}. {rationale} [{citation}]",
        rationale=rationale,
        citation=citation,
        citation_text=f"Context. {rationale}",
        confidence=0.9,
        relevant_doc_ids=(relevant_doc,),
        retrieved_doc_ids=retrieved_docs,
        relevant_rank=(retrieved_docs.index(relevant_doc) + 1 if relevant_doc in retrieved_docs else None),
    )


def test_evidence_sentence_filter_removes_tiny_fragments() -> None:
    """The evidence selector should keep substantive source sentences."""
    sentences = evidence_sentences("Tiny. This sentence is long enough to serve as grounded evidence.")
    assert sentences == ["This sentence is long enough to serve as grounded evidence."]


def test_generation_metrics_separate_retrieval_and_generation_failures() -> None:
    """Gold absence and wrong verdicts should be counted as different failures."""
    answers = [
        _answer("1", "SUPPORT", "CONTRADICT", "gold", ("wrong",)),
        _answer("2", "SUPPORT", "CONTRADICT", "gold", ("gold",)),
        _answer("3", "SUPPORT", "SUPPORT", "gold", ("gold",)),
    ]
    metrics = evaluate_answers(answers, FakeEmbeddingModel())  # type: ignore[arg-type]
    assert metrics["citation_coverage"] == 1.0
    assert metrics["citation_correctness"] == 2 / 3
    assert metrics["extractive_grounding"] == 1.0
    assert metrics["faithfulness"] == 1 / 3
    assert metrics["retrieval_failures"] == 1
    assert metrics["generation_failures"] == 1
    assert metrics["successes"] == 1
