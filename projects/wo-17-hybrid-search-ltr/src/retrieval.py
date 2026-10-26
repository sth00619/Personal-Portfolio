"""Per-query candidate retrieval and feature construction."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
RRF_RANK_CONSTANT = 60
FEATURE_COLUMNS = [
    "bm25_score", "dense_cosine", "bm25_rank", "dense_rank", "rrf_score",
    "brand_match", "title_overlap", "query_token_count", "title_token_count",
    "product_text_token_count",
]


def tokenize(text: str) -> list[str]:
    """Normalize English search text into lower-case alphanumeric tokens."""
    return TOKEN_PATTERN.findall(text.lower())


def make_features(
    examples: pd.DataFrame,
    dense_scores: np.ndarray,
) -> pd.DataFrame:
    """Build within-query BM25, dense, RRF, and lexical product features."""
    rows: list[dict[str, Any]] = []
    grouped = examples.groupby("query_id", sort=False)
    for query_id, group in grouped:
        query = str(group["query"].iloc[0])
        query_tokens = tokenize(query)
        corpus_tokens = [tokenize(str(value)) for value in group["product_text"]]
        bm25 = BM25Okapi(corpus_tokens)
        lexical_scores = np.asarray(bm25.get_scores(query_tokens), dtype=float)
        query_vector = set(query_tokens)
        products = group["product_id"].astype(str).tolist()
        candidate_dense = dense_scores[group.index.to_numpy()]
        bm25_order = np.argsort(-lexical_scores, kind="stable")
        dense_order = np.argsort(-candidate_dense, kind="stable")
        bm25_ranks = np.empty(len(group), dtype=int)
        dense_ranks = np.empty(len(group), dtype=int)
        bm25_ranks[bm25_order] = np.arange(1, len(group) + 1)
        dense_ranks[dense_order] = np.arange(1, len(group) + 1)
        fused: dict[str, float] = defaultdict(float)
        for rank, product_id in enumerate((products[index] for index in bm25_order), 1):
            fused[product_id] += 1.0 / (RRF_RANK_CONSTANT + rank)
        for rank, product_id in enumerate((products[index] for index in dense_order), 1):
            fused[product_id] += 1.0 / (RRF_RANK_CONSTANT + rank)
        for offset, (_, item) in enumerate(group.iterrows()):
            title_tokens = tokenize(str(item["product_title"]))
            brand = str(item.get("product_brand", "")).strip().lower()
            product_text_tokens = corpus_tokens[offset]
            rows.append({
                "query_id": str(query_id), "product_id": str(item["product_id"]),
                "query": query, "esci_label": str(item["esci_label"]),
                "bm25_score": float(lexical_scores[offset]),
                "dense_cosine": float(candidate_dense[offset]),
                "bm25_rank": float(bm25_ranks[offset]),
                "dense_rank": float(dense_ranks[offset]),
                "rrf_score": float(fused[str(item["product_id"])]),
                "brand_match": float(bool(brand) and brand in query.lower()),
                "title_overlap": (len(query_vector & set(title_tokens)) / len(query_vector)
                                  if query_vector else 0.0),
                "query_token_count": len(query_tokens),
                "title_token_count": len(title_tokens),
                "product_text_token_count": len(product_text_tokens),
            })
    return pd.DataFrame(rows)


def rrf_rankings(features: pd.DataFrame) -> dict[str, list[str]]:
    """Sort each query's judged candidates by its RRF fusion score."""
    ordered = features.sort_values(["query_id", "rrf_score", "product_id"],
                                   ascending=[True, False, True], kind="stable")
    return {str(query_id): group["product_id"].astype(str).tolist()
            for query_id, group in ordered.groupby("query_id", sort=False)}


def rankings_from_scores(features: pd.DataFrame, scores: np.ndarray) -> dict[str, list[str]]:
    """Sort query candidates by an arbitrary model score with deterministic ties."""
    scored = features[["query_id", "product_id"]].copy()
    scored["score"] = scores
    ordered = scored.sort_values(["query_id", "score", "product_id"],
                                 ascending=[True, False, True], kind="stable")
    return {str(query_id): group["product_id"].astype(str).tolist()
            for query_id, group in ordered.groupby("query_id", sort=False)}
