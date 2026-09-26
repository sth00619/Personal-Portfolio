"""Run full SciFact experiments or recompute the chosen CI candidate."""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import TypeVar, cast

from sentence_transformers import SentenceTransformer

from data.download import ensure_dataset
from src.evaluate import MetricSummary, Run, evaluate
from src.gate import GateResult
from src.load import load_scifact
from src.retrievers import (
    CHUNK_OVERLAP,
    EMBED_MODEL,
    RERANK_MODEL,
    bm25_runs,
    dense_runs,
    make_chunks,
    rerank_runs,
    rrf_runs,
)

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
DATASET_NAME = "BEIR SciFact test"
FULL_CHUNK_SIZES = (128, 240)
RERANK_CHUNK_SIZE = 128
T = TypeVar("T")


def write_json(path: Path, value: object) -> None:
    """Serialize one reproducible JSON result with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def timed(operation: Callable[[], T]) -> tuple[T, float]:
    """Return an operation result and elapsed wall-clock seconds."""
    started = perf_counter()
    result = operation()
    return result, perf_counter() - started


def read_baseline() -> GateResult:
    """Load the committed CI baseline using the gate's expected schema."""
    path = RESULTS / "baseline.json"
    return cast(GateResult, json.loads(path.read_text(encoding="utf-8")))


def parse_args() -> argparse.Namespace:
    """Parse the experiment mode from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "gate"), default="full")
    return parser.parse_args()


def main() -> None:
    """Run the experiment matrix or recompute the committed CI configuration."""
    args = parse_args()
    corpus, queries, qrels = load_scifact(ensure_dataset())
    print(
        f"SciFact: {len(corpus)} documents, {len(queries)} judged test queries",
        flush=True,
    )
    model = SentenceTransformer(EMBED_MODEL)
    baseline = read_baseline() if args.mode == "gate" else None
    configurations = (
        FULL_CHUNK_SIZES
        if baseline is None
        else (int(baseline["config"]["chunk_tokens"]),)
    )
    all_runs: dict[str, Run] = {}
    timings: dict[str, float] = {}
    for size in configurations:
        (chunks, parents), timings[f"chunk_{size}"] = timed(
            lambda size=size: make_chunks(corpus, model.tokenizer, size)
        )
        print(f"{size} tokens: {len(chunks)} chunks", flush=True)
        bm25, timings[f"bm25_{size}"] = timed(
            lambda: bm25_runs(chunks, parents, queries)
        )
        dense, timings[f"dense_{size}"] = timed(
            lambda size=size: dense_runs(
                model, chunks, parents, queries, RESULTS / "cache", size
            )
        )
        hybrid, timings[f"hybrid_fusion_{size}"] = timed(
            lambda: rrf_runs(bm25, dense)
        )
        all_runs[f"bm25_{size}"] = bm25
        all_runs[f"dense_{size}"] = dense
        all_runs[f"hybrid_{size}"] = hybrid
    if args.mode == "full":
        reranked, timings[f"hybrid_{RERANK_CHUNK_SIZE}_rerank"] = timed(
            lambda: rerank_runs(
                all_runs[f"hybrid_{RERANK_CHUNK_SIZE}"], corpus, queries
            )
        )
        all_runs[f"hybrid_{RERANK_CHUNK_SIZE}_rerank"] = reranked
    else:
        if baseline is None:
            raise RuntimeError("Gate mode requires a committed baseline")
        config = baseline["config"]
        name = f"{config['retriever']}_{config['chunk_tokens']}"
        if config["reranker"]:
            reranked, timings[name + "_rerank"] = timed(
                lambda: rerank_runs(all_runs[name], corpus, queries)
            )
            all_runs[name + "_rerank"] = reranked
            name += "_rerank"
        summary, _ = evaluate(all_runs[name], queries, qrels)
        write_json(
            RESULTS / "candidate.json",
            {
                "config": config,
                "dataset": DATASET_NAME,
                "summary": summary,
                "timings_seconds": timings,
            },
        )
        print(f"CI candidate recall@10: {summary['all']['recall@10']:.4f}")
        return

    summaries: dict[str, MetricSummary] = {}
    per_query: dict[str, dict[str, dict[str, float]]] = {}
    for name, run in all_runs.items():
        summaries[name], per_query[name] = evaluate(run, queries, qrels)
    write_json(
        RESULTS / "experiments.json",
        {
            "dataset": DATASET_NAME,
            "documents": len(corpus),
            "queries": len(queries),
            "embedding_model": EMBED_MODEL,
            "reranker_model": RERANK_MODEL,
            "chunk_overlap": CHUNK_OVERLAP,
            "retrieval_unit": "document (best chunk; qrels are document-level)",
            "timings_seconds": timings,
            "summary": summaries,
        },
    )
    write_json(RESULTS / "runs.json", all_runs)
    write_json(RESULTS / "per_query.json", per_query)
    print("Saved experiments.json, runs.json, per_query.json", flush=True)


if __name__ == "__main__":
    main()
