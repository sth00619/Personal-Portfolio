"""Document-level, macro-averaged retrieval metrics."""

from collections import defaultdict
from math import log2
from typing import TypeAlias

from .load import Qrels, Queries, query_category

EVALUATION_CUTOFF = 10
METRIC_NAMES = ("recall@10", "MRR", "nDCG@10")
MetricRow: TypeAlias = dict[str, float]
MetricSummary: TypeAlias = dict[str, dict[str, float | int]]
PerQueryMetrics: TypeAlias = dict[str, MetricRow]
Run: TypeAlias = dict[str, list[str]]


def query_metrics(
    ranked_docs: list[str],
    relevant: dict[str, int],
    k: int = EVALUATION_CUTOFF,
) -> MetricRow:
    """Calculate Recall@10, full-list MRR, and graded nDCG@10 for one query."""
    if not relevant:
        raise ValueError("At least one relevant document is required")
    unique = list(dict.fromkeys(ranked_docs))
    top = unique[:k]
    recall = len(set(top) & relevant.keys()) / len(relevant)
    reciprocal_rank = next((1 / rank for rank, doc in enumerate(unique, 1) if doc in relevant), 0.0)
    dcg = sum((2 ** relevant.get(doc, 0) - 1) / log2(rank + 1) for rank, doc in enumerate(top, 1))
    ideal = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / log2(rank + 1) for rank, grade in enumerate(ideal, 1))
    return {
        "recall@10": recall,
        "MRR": reciprocal_rank,
        "nDCG@10": dcg / idcg if idcg else 0.0,
    }


def evaluate(
    runs: Run,
    queries: Queries,
    qrels: Qrels,
) -> tuple[MetricSummary, PerQueryMetrics]:
    """Macro-average retrieval metrics overall and by disjoint query category."""
    buckets: defaultdict[str, list[MetricRow]] = defaultdict(list)
    per_query: PerQueryMetrics = {}
    for qid, query in queries.items():
        metrics = query_metrics(runs.get(qid, []), qrels[qid])
        per_query[qid] = metrics
        buckets["all"].append(metrics)
        buckets[query_category(query)].append(metrics)
    summary: MetricSummary = {}
    for category, rows in sorted(buckets.items()):
        summary[category] = {"n": len(rows)}
        summary[category].update(
            {key: sum(row[key] for row in rows) / len(rows) for key in METRIC_NAMES}
        )
    return summary, per_query
