from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluate import evaluate, query_metrics
from src.load import query_category
from src.retrievers import rrf_runs


def test_metrics_use_document_qrels_and_graded_gain():
    result = query_metrics(["irrelevant", "a", "a", "b"], {"a": 2, "b": 1})
    assert result["recall@10"] == 1.0
    assert result["MRR"] == 0.5
    assert 0 < result["nDCG@10"] < 1


def test_recall_counts_all_relevant_docs_even_beyond_cutoff():
    result = query_metrics(["a"], {"a": 1, "b": 1})
    assert result["recall@10"] == 0.5


def test_categories_are_disjoint_and_account_for_every_query():
    queries = {"1": "No effect of treatment", "2": "Rate increases 20 percent", "3": "Protein expression changes"}
    qrels = {qid: {qid: 1} for qid in queries}
    runs = {qid: [qid] for qid in queries}
    summary, _ = evaluate(runs, queries, qrels)
    assert sum(row["n"] for key, row in summary.items() if key != "all") == summary["all"]["n"] == 3
    assert query_category(queries["1"]) == "negation"


def test_rrf_favors_consensus_doc():
    result = rrf_runs({"q": ["a", "b"]}, {"q": ["b", "c"]})
    assert result["q"][0] == "b"
