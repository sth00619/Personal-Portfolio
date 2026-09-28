"""Run threshold tuning, 1,000-query cache replay, and artifact generation."""

import json
import os
from pathlib import Path
from typing import cast

import numpy as np
import redis
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

from data.download import DATASET_REVISION, ensure_dataset
from src.cache import RedisClient, ThreeTierCache
from src.dashboard import (
    render_dashboard,
    render_dashboard_html,
    render_precision_curve,
    write_curve_csv,
)
from src.data import build_replay_events, load_experiment_pairs
from src.evaluate import (
    TARGET_PRECISION,
    THRESHOLD_SAFETY_MARGIN,
    select_threshold,
    summarize_replay,
    threshold_curve,
)
from src.models import CacheContext, CachedAnswer, ReplayRecord
from src.report import build_report
from src.simulator import (
    INPUT_PRICE_PER_MILLION,
    OUTPUT_PRICE_PER_MILLION,
    PREFIX_INPUT_DISCOUNT,
    PREFIX_LATENCY_SAVING_MS,
    SYSTEM_PROMPT_TOKENS,
    simulate_request,
)

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIRECTORY = PROJECT_ROOT / "results"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
EMBEDDING_MODEL = "sentence-transformers/quora-distilbert-base"
EMBED_BATCH_SIZE = 128
MODEL_MAX_SEQUENCE_LENGTH = 256
TTL_SECONDS = 3_600
PROMPT_V1 = "support-policy-v1"
PROMPT_V2 = "support-policy-v2"


def write_json(path: Path, value: object) -> None:
    """Write a deterministic UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def encode_texts(
    model: SentenceTransformer, texts: list[str]
) -> NDArray[np.float32]:
    """Encode and normalize a list of questions for cosine search."""
    vectors = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def demonstrate_cache_bust(
    cache: ThreeTierCache,
    vector: NDArray[np.float32],
) -> dict[str, object]:
    """Show that a prompt-version change cannot reuse the prior response."""
    cache.reset_namespace()
    question = "How can I reset my account password?"
    common = {
        "model": "local-qa-simulator-v1",
        "temperature": 0.0,
        "tools": ("knowledge_search",),
        "tenant_id": "cache-bust-demo",
        "customer_tier": "standard",
    }
    context_v1 = CacheContext(system_prompt_version=PROMPT_V1, **common)
    context_v2 = CacheContext(system_prompt_version=PROMPT_V2, **common)
    first_v1 = cache.lookup(question, context_v1, vector)
    cache.store_response(
        question,
        context_v1,
        vector,
        CachedAnswer("Password reset instructions v1", "password-reset"),
    )
    second_v1 = cache.lookup(question, context_v1, vector)
    first_v2 = cache.lookup(question, context_v2, vector)
    invalidated = cache.invalidate_prompt_version(PROMPT_V1)
    return {
        "first_v1_lookup": first_v1.level,
        "second_v1_lookup": second_v1.level,
        "first_v2_lookup": first_v2.level,
        "prompt_change_busted_cache": first_v2.level == "miss",
        "invalidated": invalidated,
    }


def main() -> None:
    """Tune a safe threshold, replay traffic, and render measured artifacts."""
    dataset_path = ensure_dataset()
    tuning_pairs, replay_pairs = load_experiment_pairs(dataset_path)
    model = SentenceTransformer(EMBEDDING_MODEL)
    model.max_seq_length = MODEL_MAX_SEQUENCE_LENGTH

    tuning_first = encode_texts(model, [pair.question1 for pair in tuning_pairs])
    tuning_second = encode_texts(model, [pair.question2 for pair in tuning_pairs])
    similarities = np.sum(tuning_first * tuning_second, axis=1)
    labels = np.asarray([pair.safe_to_reuse for pair in tuning_pairs], dtype=np.bool_)
    curve = threshold_curve(similarities, labels)
    selected_threshold = select_threshold(curve)
    selected_row = next(
        row for row in curve if float(row["threshold"]) == selected_threshold
    )

    client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
    client.ping()
    cache = ThreeTierCache(cast(RedisClient, client), selected_threshold, TTL_SECONDS)
    cache.reset_namespace()
    events = build_replay_events(replay_pairs)
    replay_vectors = encode_texts(model, [event.question for event in events])
    records: list[ReplayRecord] = []
    for event, vector in zip(events, replay_vectors):
        lookup = cache.lookup(event.question, event.context, vector)
        outcome = simulate_request(event, lookup.level)
        valid_hit = (
            lookup.cached_answer.intent_id == event.intent_id
            if lookup.cached_answer is not None
            else None
        )
        if lookup.cached_answer is None:
            cache.store_response(event.question, event.context, vector, outcome.answer)
        records.append(
            ReplayRecord(
                event_id=event.event_id,
                pair_id=event.pair_id,
                request_kind=event.request_kind,
                cache_level=lookup.level,
                valid_hit=valid_hit,
                similarity=lookup.similarity,
                baseline_cost_usd=outcome.baseline_cost_usd,
                actual_cost_usd=outcome.actual_cost_usd,
                baseline_latency_ms=outcome.baseline_latency_ms,
                actual_latency_ms=outcome.actual_latency_ms,
            )
        )

    replay_metrics = summarize_replay(records)
    demo_vector = encode_texts(model, ["How can I reset my account password?"])[0]
    cache_bust = demonstrate_cache_bust(cache, demo_vector)
    experiment = {
        "dataset": "Quora Question Pairs via sentence-transformers/quora-duplicates",
        "dataset_revision": DATASET_REVISION,
        "embedding_model": EMBEDDING_MODEL,
        "tuning_pairs": len(tuning_pairs),
        "replay_pairs": len(replay_pairs),
        "normalized_label_overrides": sum(
            pair.safe_to_reuse != pair.label_duplicate
            for pair in tuning_pairs + replay_pairs
        ),
        "threshold_tuning": {
            "selected_threshold": selected_threshold,
            "precision_policy": TARGET_PRECISION,
            "safety_margin": THRESHOLD_SAFETY_MARGIN,
            "selected_precision": selected_row["precision"],
            "selected_recall": selected_row["recall"],
            "selected_coverage": selected_row["coverage"],
            "selected_true_hits": selected_row["true_hits"],
            "selected_false_hits": selected_row["false_hits"],
        },
        "replay": replay_metrics,
        "cache_bust": cache_bust,
        "simulation_assumptions": {
            "input_price_per_million_usd": INPUT_PRICE_PER_MILLION,
            "output_price_per_million_usd": OUTPUT_PRICE_PER_MILLION,
            "system_prompt_tokens": SYSTEM_PROMPT_TOKENS,
            "prefix_input_discount": PREFIX_INPUT_DISCOUNT,
            "prefix_latency_saving_ms": PREFIX_LATENCY_SAVING_MS,
            "boundary": "Redis and FAISS are executed; LLM cost and latency are deterministic modeled values.",
        },
    }
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    write_json(RESULTS_DIRECTORY / "experiment.json", experiment)
    write_json(
        RESULTS_DIRECTORY / "replay_records.json",
        [record.to_dict() for record in records],
    )
    write_curve_csv(RESULTS_DIRECTORY / "precision_curve.csv", curve)
    render_precision_curve(
        RESULTS_DIRECTORY / "precision_curve.png", curve, selected_threshold
    )
    render_dashboard(
        RESULTS_DIRECTORY / "dashboard.png", replay_metrics, selected_threshold
    )
    render_dashboard_html(
        RESULTS_DIRECTORY / "dashboard.html", replay_metrics, selected_threshold
    )
    build_report(RESULTS_DIRECTORY / "report.md", experiment)
    print(
        f"Replay complete: response hit rate {float(replay_metrics['response_hit_rate']):.2%}, "
        f"semantic false-hit rate {float(replay_metrics['semantic_false_hit_rate']):.2%}",
        flush=True,
    )


if __name__ == "__main__":
    main()
