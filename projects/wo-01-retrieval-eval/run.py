"""Run full SciFact experiments or recompute the chosen CI candidate."""

import argparse
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

from data.download import ensure_dataset
from src.evaluate import evaluate
from src.load import load_scifact
from src.retrievers import EMBED_MODEL, RERANK_MODEL, bm25_runs, dense_runs, make_chunks, rerank_runs, rrf_runs

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "gate"), default="full")
    args = parser.parse_args()
    corpus, queries, qrels = load_scifact(ensure_dataset())
    print(f"SciFact: {len(corpus)} documents, {len(queries)} judged test queries", flush=True)
    model = SentenceTransformer(EMBED_MODEL)
    configurations = [128, 240] if args.mode == "full" else [json.loads((RESULTS / "baseline.json").read_text(encoding="utf-8"))["config"]["chunk_tokens"]]
    all_runs = {}
    for size in configurations:
        chunks, parents = make_chunks(corpus, model.tokenizer, size)
        print(f"{size} tokens: {len(chunks)} chunks", flush=True)
        bm25 = bm25_runs(chunks, parents, queries)
        dense = dense_runs(model, chunks, parents, queries, RESULTS / "cache", size)
        hybrid = rrf_runs(bm25, dense)
        all_runs[f"bm25_{size}"] = bm25
        all_runs[f"dense_{size}"] = dense
        all_runs[f"hybrid_{size}"] = hybrid
    if args.mode == "full":
        all_runs["hybrid_128_rerank"] = rerank_runs(all_runs["hybrid_128"], corpus, queries)
    else:
        config = json.loads((RESULTS / "baseline.json").read_text(encoding="utf-8"))["config"]
        name = f"{config['retriever']}_{config['chunk_tokens']}"
        if config["reranker"]:
            all_runs[name + "_rerank"] = rerank_runs(all_runs[name], corpus, queries)
            name += "_rerank"
        summary, _ = evaluate(all_runs[name], queries, qrels)
        write_json(RESULTS / "candidate.json", {"config": config, "dataset": "BEIR SciFact test", "summary": summary})
        print(f"CI candidate recall@10: {summary['all']['recall@10']:.4f}")
        return

    summaries, per_query = {}, {}
    for name, run in all_runs.items():
        summaries[name], per_query[name] = evaluate(run, queries, qrels)
    write_json(RESULTS / "experiments.json", {
        "dataset": "BEIR SciFact test", "documents": len(corpus), "queries": len(queries),
        "embedding_model": EMBED_MODEL, "reranker_model": RERANK_MODEL,
        "chunk_overlap": 24, "retrieval_unit": "document (best chunk; qrels are document-level)",
        "summary": summaries,
    })
    write_json(RESULTS / "runs.json", all_runs)
    write_json(RESULTS / "per_query.json", per_query)
    print("Saved experiments.json, runs.json, per_query.json", flush=True)


if __name__ == "__main__":
    main()
