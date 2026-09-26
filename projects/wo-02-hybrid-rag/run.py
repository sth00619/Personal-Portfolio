"""Run WO-02 retrieval, grounded generation, and separated evaluation."""

import json
from pathlib import Path
from time import perf_counter

from sentence_transformers import CrossEncoder, SentenceTransformer

from data.download import ensure_dataset
from src.analyze import build_failure_analysis
from src.evaluate import evaluate_answers, evaluate_run
from src.generate import NLI_MODEL, generate_answers
from src.load import load_eval_questions, load_scifact
from src.report import build_report
from src.retrieval import (
    CHUNK_OVERLAP,
    CHUNK_TOKENS,
    EMBEDDING_MODEL,
    RERANK_MODEL,
    HybridIndex,
    chunk_corpus,
    retrieve_all_stages,
)

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIRECTORY = PROJECT_ROOT / "results"
CACHE_DIRECTORY = PROJECT_ROOT / "artifacts" / "cache"
QUESTION_SELECTION = PROJECT_ROOT / "data" / "questions.json"
DATASET_NAME = "BEIR SciFact test"
MODEL_MAX_LENGTH = 512


def write_json(path: Path, value: object) -> None:
    """Write a deterministic UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Build indexes, compare retrieval stages, and evaluate cited answers."""
    started = perf_counter()
    dataset_path = ensure_dataset()
    corpus, queries, qrels = load_scifact(dataset_path)
    questions = load_eval_questions(dataset_path, QUESTION_SELECTION)
    print(
        f"SciFact: {len(corpus)} documents, {len(queries)} retrieval queries, "
        f"{len(questions)} generation questions",
        flush=True,
    )

    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    chunks = chunk_corpus(corpus, embedding_model.tokenizer)
    print(f"Indexed chunks: {len(chunks)}", flush=True)
    index = HybridIndex(chunks, embedding_model, CACHE_DIRECTORY)
    reranker = CrossEncoder(RERANK_MODEL, max_length=MODEL_MAX_LENGTH)
    runs, contexts = retrieve_all_stages(index, queries, reranker)
    retrieval_metrics = {
        stage: evaluate_run(run, qrels) for stage, run in runs.items()
    }

    nli_model = CrossEncoder(NLI_MODEL, max_length=MODEL_MAX_LENGTH)
    answers = generate_answers(questions, contexts, nli_model)
    generation_metrics = evaluate_answers(answers, embedding_model)
    failure_analysis = build_failure_analysis(
        queries, qrels, runs["hybrid_rerank"], answers
    )
    bm25_recall = float(retrieval_metrics["bm25"]["recall@10"])
    final_recall = float(retrieval_metrics["hybrid_rerank"]["recall@10"])
    bm25_ndcg = float(retrieval_metrics["bm25"]["nDCG@10"])
    final_ndcg = float(retrieval_metrics["hybrid_rerank"]["nDCG@10"])
    experiment = {
        "dataset": DATASET_NAME,
        "documents": len(corpus),
        "retrieval_queries": len(queries),
        "generation_questions": len(questions),
        "chunks": len(chunks),
        "chunk_tokens": CHUNK_TOKENS,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL,
        "reranker_model": RERANK_MODEL,
        "nli_model": NLI_MODEL,
        "retrieval": retrieval_metrics,
        "improvement_over_bm25": {
            "recall@10_percentage_points": (final_recall - bm25_recall) * 100,
            "nDCG@10_percentage_points": (final_ndcg - bm25_ndcg) * 100,
        },
        "generation": generation_metrics,
        "elapsed_seconds": perf_counter() - started,
    }
    write_json(RESULTS_DIRECTORY / "experiments.json", experiment)
    write_json(
        RESULTS_DIRECTORY / "answers.json",
        [answer.to_dict() for answer in answers],
    )
    write_json(RESULTS_DIRECTORY / "failure_analysis.json", failure_analysis)
    build_report()
    print(
        f"Hybrid+rerank Recall@10: {final_recall:.4f}; "
        f"faithfulness: {float(generation_metrics['faithfulness']):.4f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
