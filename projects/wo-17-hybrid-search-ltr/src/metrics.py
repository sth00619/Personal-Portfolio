"""Ranking metrics for ESCI binary and graded relevance."""

from __future__ import annotations

import math
from collections.abc import Sequence

LABELS = {"I": 0, "C": 1, "S": 2, "E": 3}
RANKING_CUTOFF = 10


def ndcg_at_k(relevances: Sequence[int], cutoff: int = RANKING_CUTOFF) -> float:
    """Compute NDCG with exponential gain and logarithmic rank discount."""
    ranked = list(relevances[:cutoff])
    ideal = sorted(relevances, reverse=True)[:cutoff]

    def dcg(values: Sequence[int]) -> float:
        return sum((2**value - 1) / math.log2(rank + 2)
                   for rank, value in enumerate(values))

    ideal_score = dcg(ideal)
    return dcg(ranked) / ideal_score if ideal_score else 0.0


def mrr_at_k(relevances: Sequence[int], cutoff: int = RANKING_CUTOFF) -> float:
    """Return reciprocal rank of the first relevant item within the cutoff."""
    for rank, relevance in enumerate(relevances[:cutoff], start=1):
        if relevance > 0:
            return 1.0 / rank
    return 0.0


def evaluate_rankings(
    ranked_ids: dict[str, list[str]], labels_by_query: dict[str, dict[str, str]],
) -> dict[str, float | int]:
    """Score ranked products with exact-only binary and four-level graded labels."""
    binary_ndcg: list[float] = []
    binary_mrr: list[float] = []
    graded_ndcg: list[float] = []
    graded_mrr: list[float] = []
    for query_id, ranked in ranked_ids.items():
        query_labels = labels_by_query[query_id]
        binary = [int(query_labels[product_id] == "E") for product_id in ranked]
        graded = [LABELS[query_labels[product_id]] for product_id in ranked]
        all_binary = [int(label == "E") for label in query_labels.values()]
        all_graded = [LABELS[label] for label in query_labels.values()]
        binary_ndcg.append(ndcg_at_k(binary, RANKING_CUTOFF) if any(all_binary) else 0.0)
        binary_mrr.append(mrr_at_k(binary, RANKING_CUTOFF))
        graded_ndcg.append(ndcg_at_k(graded, RANKING_CUTOFF))
        graded_mrr.append(mrr_at_k(graded, RANKING_CUTOFF))
    return {
        "queries": len(ranked_ids),
        "binary_exact_ndcg_at_10": sum(binary_ndcg) / len(binary_ndcg),
        "binary_exact_mrr_at_10": sum(binary_mrr) / len(binary_mrr),
        "graded_esci_ndcg_at_10": sum(graded_ndcg) / len(graded_ndcg),
        "graded_esci_mrr_at_10": sum(graded_mrr) / len(graded_mrr),
    }
