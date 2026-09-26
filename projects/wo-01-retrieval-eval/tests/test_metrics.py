from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluate import evaluate, query_metrics
from src.gate import GateResult, assert_recall_within_tolerance
from src.load import query_category
from src.retrievers import rrf_runs


def test_metrics_use_document_qrels_and_graded_gain() -> None:
    """Metric calculation should deduplicate documents and honor graded gains."""
    result = query_metrics(["irrelevant", "a", "a", "b"], {"a": 2, "b": 1})
    assert result["recall@10"] == 1.0
    assert result["MRR"] == 0.5
    assert 0 < result["nDCG@10"] < 1


def test_recall_counts_all_relevant_docs_even_beyond_cutoff() -> None:
    """Recall denominator should contain every judged relevant document."""
    result = query_metrics(["a"], {"a": 1, "b": 1})
    assert result["recall@10"] == 0.5


def test_categories_are_disjoint_and_account_for_every_query() -> None:
    """Heuristic categories should be mutually exclusive and exhaustive."""
    queries = {
        "1": "No effect of treatment",
        "2": "Rate increases 20 percent",
        "3": "Protein expression changes",
    }
    qrels = {qid: {qid: 1} for qid in queries}
    runs = {qid: [qid] for qid in queries}
    summary, _ = evaluate(runs, queries, qrels)
    assert sum(row["n"] for key, row in summary.items() if key != "all") == summary["all"]["n"] == 3
    assert query_category(queries["1"]) == "negation"


def test_rrf_favors_consensus_doc() -> None:
    """RRF should rank a document seen by both inputs above single-list hits."""
    result = rrf_runs({"q": ["a", "b"]}, {"q": ["b", "c"]})
    assert result["q"][0] == "b"


def _gate_result(recall: float) -> GateResult:
    """Build the smallest valid gate result for a unit-level threshold check."""
    return {
        "config": {
            "retriever": "hybrid",
            "chunk_tokens": 128,
            "reranker": False,
        },
        "summary": {"all": {"n": 300, "recall@10": recall}},
    }


def test_gate_accepts_exactly_one_percentage_point_drop() -> None:
    """A candidate exactly at the documented tolerance should pass."""
    assert_recall_within_tolerance(_gate_result(0.82), _gate_result(0.81))


def test_gate_rejects_more_than_one_percentage_point_drop() -> None:
    """A candidate below the documented tolerance should fail with its values."""
    with pytest.raises(AssertionError, match=r"0\.8099 < 0\.8100"):
        assert_recall_within_tolerance(_gate_result(0.82), _gate_result(0.8099))
