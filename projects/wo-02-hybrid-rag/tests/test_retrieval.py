"""Unit tests for ranking and document-level retrieval metrics."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluate import query_metrics
from src.models import SearchHit
from src.retrieval import rrf_fuse


def _hit(doc_id: str, score: float) -> SearchHit:
    """Build a minimal search hit for fusion tests."""
    return SearchHit(f"{doc_id}#c0", doc_id, f"text {doc_id}", score)


def test_metrics_deduplicate_documents_and_use_graded_gain() -> None:
    """Evaluation should use unique document IDs and graded nDCG gains."""
    metrics = query_metrics(["x", "a", "a", "b"], {"a": 2, "b": 1})
    assert metrics["recall@10"] == 1.0
    assert metrics["MRR"] == 0.5
    assert 0.0 < metrics["nDCG@10"] < 1.0


def test_rrf_promotes_a_document_found_by_both_retrievers() -> None:
    """RRF should favor consensus over a first-place single-list result."""
    fused = rrf_fuse([_hit("a", 9.0), _hit("b", 8.0)], [_hit("b", 0.9), _hit("c", 0.8)])
    assert fused[0].doc_id == "b"
