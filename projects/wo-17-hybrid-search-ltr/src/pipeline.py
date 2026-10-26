"""Train and evaluate a hybrid ESCI search pipeline with LambdaMART."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as ds
from sentence_transformers import SentenceTransformer

from .metrics import LABELS, evaluate_rankings
from .retrieval import FEATURE_COLUMNS, make_features, rankings_from_scores, rrf_rankings

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = ROOT / "cache"
RESULTS_DIR = ROOT / "results"
EXAMPLES_FILE = "shopping_queries_dataset_examples.parquet"
PRODUCTS_FILE = "shopping_queries_dataset_products.parquet"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
PRODUCT_COLUMNS = ["product_id", "product_locale", "product_title", "product_description",
                   "product_bullet_point", "product_brand", "product_color"]
EMBED_BATCH_SIZE = 128
PRODUCT_MAX_TOKENS = 192
RANKER_SEED = 1707


def load_task1_data() -> pd.DataFrame:
    """Load US Task 1 small-version labels and only their catalog products."""
    examples_path = RAW_DIR / EXAMPLES_FILE
    products_path = RAW_DIR / PRODUCTS_FILE
    examples = pd.read_parquet(examples_path)
    examples = examples.loc[
        (examples["small_version"] == 1) & (examples["product_locale"] == "us")
    ].copy()
    examples["query_id"] = examples["query_id"].astype(str)
    examples["product_id"] = examples["product_id"].astype(str)
    product_ids = set(examples["product_id"])
    product_dataset = ds.dataset(products_path, format="parquet")
    filter_expression = (
        (ds.field("product_locale") == "us")
        & ds.field("product_id").isin(sorted(product_ids))
    )
    scanner = product_dataset.scanner(columns=PRODUCT_COLUMNS, filter=filter_expression,
                                      batch_size=100_000, use_threads=True)
    product_batches = [batch.to_pandas() for batch in scanner.to_batches()]
    if not product_batches:
        raise ValueError("No US product rows matched the Task 1 small-version query set")
    products = pd.concat(product_batches, ignore_index=True)
    products["product_id"] = products["product_id"].astype(str)
    products = products.drop_duplicates(["product_locale", "product_id"])
    merged = examples.merge(products, on=["product_locale", "product_id"], how="left",
                            validate="many_to_one")
    missing = int(merged["product_title"].isna().sum())
    if missing:
        raise ValueError(f"Missing product titles after locale/id join: {missing}")
    for column in PRODUCT_COLUMNS[2:]:
        merged[column] = merged[column].fillna("").astype(str)
    merged["product_text"] = merged.apply(_product_text, axis=1)
    return merged.reset_index(drop=True)


def _product_text(row: pd.Series) -> str:
    """Compose a bounded product representation for dense and lexical retrieval."""
    fields = [row["product_title"], row["product_brand"], row["product_color"],
              row["product_bullet_point"], row["product_description"]]
    return " ".join(str(field).strip() for field in fields if str(field).strip())[:5000]


def _fingerprint(items: list[str]) -> str:
    """Build a stable cache key from ordered query or product content."""
    digest = hashlib.sha256()
    for item in items:
        digest.update(item.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:20]


def encode_examples(examples: pd.DataFrame) -> np.ndarray:
    """Encode unique catalog items and query text, then score each judged pair."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    product_map = examples.drop_duplicates(["product_locale", "product_id"])
    product_keys = [f"{row.product_locale}:{row.product_id}"
                    for row in product_map.itertuples(index=False)]
    product_texts = product_map["product_text"].tolist()
    query_map = examples[["query_id", "query"]].drop_duplicates("query_id")
    query_ids = query_map["query_id"].astype(str).tolist()
    query_texts = query_map["query"].astype(str).tolist()
    model = SentenceTransformer(EMBEDDING_MODEL, revision=EMBEDDING_REVISION,
                                device=_embedding_device())
    model.max_seq_length = PRODUCT_MAX_TOKENS
    model_identity = [EMBEDDING_MODEL, EMBEDDING_REVISION]
    product_cache = CACHE_DIR / f"products-{_fingerprint(model_identity + product_keys)}.npy"
    query_cache = CACHE_DIR / f"queries-{_fingerprint(model_identity + query_ids + query_texts)}.npy"
    product_vectors = _load_or_encode(model, product_texts, product_cache)
    query_vectors = _load_or_encode(model, query_texts, query_cache)
    product_index = {key: index for index, key in enumerate(product_keys)}
    query_index = {query_id: index for index, query_id in enumerate(query_ids)}
    product_positions = np.fromiter(
        (product_index[f"{row.product_locale}:{row.product_id}"]
         for row in examples.itertuples(index=False)), dtype=np.int64, count=len(examples)
    )
    query_positions = examples["query_id"].map(query_index).to_numpy(dtype=np.int64)
    return np.einsum("ij,ij->i", query_vectors[query_positions],
                     product_vectors[product_positions], optimize=True)


def _embedding_device() -> str:
    """Select Apple Metal when available, otherwise use CPU inference."""
    try:
        import torch
        return "mps" if torch.backends.mps.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _load_or_encode(model: SentenceTransformer, texts: list[str], cache_path: Path) -> np.ndarray:
    """Reuse a model/content-keyed embedding cache or compute normalized vectors."""
    if cache_path.exists():
        return np.load(cache_path, mmap_mode="r")
    embeddings = model.encode(texts, batch_size=EMBED_BATCH_SIZE,
                              normalize_embeddings=True, convert_to_numpy=True,
                              show_progress_bar=True).astype(np.float32)
    np.save(cache_path, embeddings)
    return embeddings


def _prepare_ranker_rows(features: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """Sort rows by query and return contiguous LightGBM query group sizes."""
    ordered = features.sort_values(["query_id", "product_id"], kind="stable").reset_index(drop=True)
    group_sizes = ordered.groupby("query_id", sort=False).size().astype(int).tolist()
    return ordered, group_sizes


def _query_labels(frame: pd.DataFrame) -> dict[str, dict[str, str]]:
    """Create per-query judgement maps used by ranking metrics."""
    return {
        str(query_id): dict(zip(group["product_id"].astype(str), group["esci_label"].astype(str)))
        for query_id, group in frame.groupby("query_id", sort=False)
    }


def run_pipeline() -> dict[str, Any]:
    """Build retrieval features, fit LambdaMART on train, and score held-out test."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    examples = load_task1_data()
    print(f"Loaded {len(examples):,} judged pairs across "
          f"{examples['query_id'].nunique():,} US Task 1 queries", flush=True)
    dense_scores = encode_examples(examples)
    features = make_features(examples, dense_scores)
    features["split"] = features["query_id"].map(
        examples.drop_duplicates("query_id").set_index("query_id")["split"]
    )
    train = features.loc[features["split"] == "train"].copy()
    test = features.loc[features["split"] == "test"].copy()
    train, train_groups = _prepare_ranker_rows(train)
    test = test.reset_index(drop=True)
    if train["query_id"].isin(test["query_id"]).any():
        raise ValueError("Official query-level train/test split overlaps")
    ranker = lgb.LGBMRanker(
        objective="lambdarank", metric="ndcg", n_estimators=300,
        learning_rate=0.05, num_leaves=31, min_child_samples=50,
        label_gain=[0, 1, 3, 7], random_state=RANKER_SEED,
        importance_type="gain", verbosity=-1, n_jobs=-1,
    )
    ranker.fit(train[FEATURE_COLUMNS], train["esci_label"].map(LABELS).astype(int),
               group=train_groups)
    test_scores = ranker.predict(test[FEATURE_COLUMNS])
    baseline_rankings = rrf_rankings(test)
    ltr_rankings = rankings_from_scores(test, test_scores)
    labels = _query_labels(test)
    hybrid_metrics = evaluate_rankings(baseline_rankings, labels)
    ltr_metrics = evaluate_rankings(ltr_rankings, labels)
    metric_names = ["binary_exact_ndcg_at_10", "binary_exact_mrr_at_10",
                    "graded_esci_ndcg_at_10", "graded_esci_mrr_at_10"]
    metric_deltas = {name: float(ltr_metrics[name] - hybrid_metrics[name])
                     for name in metric_names}
    raw_importance = ranker.feature_importances_.astype(float)
    total_gain = float(raw_importance.sum())
    importance = [
        {"feature": FEATURE_COLUMNS[index], "gain": float(value),
         "gain_share_pct": (float(value) / total_gain * 100 if total_gain else 0.0)}
        for index, value in sorted(enumerate(raw_importance), key=lambda pair: -pair[1])
    ]
    source_manifest = json.loads(
        (ROOT / "docs" / "source_manifest.json").read_text(encoding="utf-8")
    )
    metrics = {
        "dataset": "Amazon Science Shopping Queries Dataset, Task 1 small_version, US",
        "dataset_revision": source_manifest["repository_revision"],
        "source_sha256": {name: item["sha256"]
                          for name, item in source_manifest["files"].items()},
        "embedding_model": {"name": EMBEDDING_MODEL, "revision": EMBEDDING_REVISION},
        "embedding_device": _embedding_device(),
        "retrieval_parameters": {
            "bm25": "rank_bm25.BM25Okapi defaults",
            "rrf_rank_constant": 60,
            "embedding_max_sequence_length": PRODUCT_MAX_TOKENS,
            "embedding_batch_size": EMBED_BATCH_SIZE,
            "candidate_scope": "all judged products for each query only",
        },
        "ltr_model": "LightGBM LambdaMART; graded labels E=3, S=2, C=1, I=0",
        "ltr_parameters": {
            "objective": "lambdarank", "n_estimators": 300,
            "learning_rate": 0.05, "num_leaves": 31,
            "min_child_samples": 50, "label_gain": [0, 1, 3, 7],
            "random_state": RANKER_SEED, "n_jobs": -1,
        },
        "evaluation": {
            "test_queries": len(labels),
            "train_queries": train["query_id"].nunique(),
            "test_query_product_pairs": len(test),
            "train_query_product_pairs": len(train),
            "max_candidates_per_query": int(examples.groupby("query_id").size().max()),
            "max_train_candidates_per_query": int(train.groupby("query_id").size().max()),
            "max_test_candidates_per_query": int(test.groupby("query_id").size().max()),
            "train_unique_products": int(train["product_id"].nunique()),
            "test_unique_products": int(test["product_id"].nunique()),
            "unique_products_across_splits": int(examples["product_id"].nunique()),
            "test_candidate_depth": _candidate_depth_summary(test),
            "features": FEATURE_COLUMNS,
            "binary_positive_label": "E only",
            "graded_relevance": {"E": 3, "S": 2, "C": 1, "I": 0},
            "ndcg_gain": "2^relevance - 1; discount log2(rank + 1)",
            "mrr_binary": "reciprocal rank of the first Exact (E), cutoff 10",
            "mrr_graded": "reciprocal rank of first non-I item, cutoff 10",
            "hybrid_rrf": hybrid_metrics,
            "hybrid_plus_ltr": ltr_metrics,
            "ltr_minus_hybrid_delta": metric_deltas,
            "ndcg_conclusion": {
                "binary_exact": "improved" if metric_deltas["binary_exact_ndcg_at_10"] > 0
                else "unchanged" if metric_deltas["binary_exact_ndcg_at_10"] == 0 else "declined",
                "graded_esci": "improved" if metric_deltas["graded_esci_ndcg_at_10"] > 0
                else "unchanged" if metric_deltas["graded_esci_ndcg_at_10"] == 0 else "declined",
            },
        },
        "feature_importance_gain": importance,
        "label_distribution_train": train["esci_label"].value_counts().sort_index().to_dict(),
        "label_distribution_test": test["esci_label"].value_counts().sort_index().to_dict(),
    }
    (RESULTS_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(metrics["feature_importance_gain"]).to_csv(
        RESULTS_DIR / "feature_importance.csv", index=False
    )
    return metrics


def _candidate_depth_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    """Summarize the number of judged products available for each query."""
    depths = frame.groupby("query_id").size().to_numpy(dtype=float)
    return {
        "min": int(depths.min()), "mean": float(depths.mean()),
        "median": float(np.median(depths)), "p90": float(np.quantile(depths, 0.90)),
        "p95": float(np.quantile(depths, 0.95)), "p99": float(np.quantile(depths, 0.99)),
        "max": int(depths.max()),
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), ensure_ascii=False, indent=2))
