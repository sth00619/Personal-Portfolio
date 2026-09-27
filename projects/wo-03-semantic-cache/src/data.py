"""Load deterministic Quora subsets and construct replay traffic."""

from pathlib import Path
import re

import duckdb

from .models import CacheContext, QuestionPair, ReplayEvent

TUNING_PER_LABEL = 1_000
SEMANTIC_REPLAY_PER_LABEL = 175
EXACT_REPLAY_PER_LABEL = 75
REPLAY_QUERY_COUNT = 1_000
MODEL_NAME = "local-qa-simulator-v1"
TEMPERATURE = 0.0
SYSTEM_PROMPT_VERSION = "support-policy-v1"
TOOLS = ("knowledge_search",)
CANONICAL_PATTERN = re.compile(r"[A-Za-z0-9]+")


def canonical_question(question: str) -> str:
    """Remove casing, punctuation, and spacing for deterministic label-noise review."""
    return "".join(CANONICAL_PATTERN.findall(question.casefold()))


def _read_label_slice(
    dataset_path: Path, label: int, offset: int, limit: int
) -> list[QuestionPair]:
    """Read a deterministic label-balanced slice from the parquet dataset."""
    query = """
        SELECT sentence1, sentence2, label
        FROM read_parquet(?)
        WHERE label = ?
          AND sentence1 IS NOT NULL
          AND sentence2 IS NOT NULL
          AND length(trim(sentence1)) > 0
          AND length(trim(sentence2)) > 0
        ORDER BY hash(sentence1 || chr(0) || sentence2)
        LIMIT ? OFFSET ?
    """
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            query, [str(dataset_path), label, limit, offset]
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != limit:
        raise ValueError(f"Expected {limit} rows for label {label}, found {len(rows)}")
    pairs: list[QuestionPair] = []
    for first, second, value in rows:
        question1 = str(first)
        question2 = str(second)
        label_duplicate = bool(value)
        exact_after_normalization = canonical_question(question1) == canonical_question(question2)
        pairs.append(
            QuestionPair(
                question1,
                question2,
                label_duplicate,
                label_duplicate or exact_after_normalization,
            )
        )
    return pairs


def load_experiment_pairs(dataset_path: Path) -> tuple[list[QuestionPair], list[QuestionPair]]:
    """Return non-overlapping tuning and replay pairs with balanced labels."""
    tuning = _read_label_slice(dataset_path, 0, 0, TUNING_PER_LABEL)
    tuning += _read_label_slice(dataset_path, 1, 0, TUNING_PER_LABEL)
    replay_limit = SEMANTIC_REPLAY_PER_LABEL + EXACT_REPLAY_PER_LABEL
    negatives = _read_label_slice(dataset_path, 0, TUNING_PER_LABEL, replay_limit)
    positives = _read_label_slice(dataset_path, 1, TUNING_PER_LABEL, replay_limit)
    semantic = negatives[:SEMANTIC_REPLAY_PER_LABEL]
    semantic += positives[:SEMANTIC_REPLAY_PER_LABEL]
    exact = negatives[SEMANTIC_REPLAY_PER_LABEL:]
    exact += positives[SEMANTIC_REPLAY_PER_LABEL:]
    return tuning, semantic + exact


def build_replay_events(pairs: list[QuestionPair]) -> list[ReplayEvent]:
    """Create two requests per pair: a cold seed followed by exact or semantic reuse."""
    semantic_pair_count = SEMANTIC_REPLAY_PER_LABEL * 2
    events: list[ReplayEvent] = []
    for pair_id, pair in enumerate(pairs):
        tier = "enterprise" if pair_id % 2 == 0 else "standard"
        context = CacheContext(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            tools=TOOLS,
            system_prompt_version=SYSTEM_PROMPT_VERSION,
            tenant_id=f"tenant-{pair_id:04d}",
            customer_tier=tier,
        )
        first_intent = f"pair-{pair_id}:intent-a"
        events.append(
            ReplayEvent(
                event_id=len(events),
                pair_id=pair_id,
                question=pair.question1,
                intent_id=first_intent,
                request_kind="seed",
                context=context,
            )
        )
        if pair_id < semantic_pair_count:
            second_question = pair.question2
            second_intent = (
                first_intent if pair.safe_to_reuse else f"pair-{pair_id}:intent-b"
            )
            request_kind = (
                "semantic_duplicate" if pair.safe_to_reuse else "semantic_distinct"
            )
        else:
            second_question = pair.question1
            second_intent = first_intent
            request_kind = "exact_repeat"
        events.append(
            ReplayEvent(
                event_id=len(events),
                pair_id=pair_id,
                question=second_question,
                intent_id=second_intent,
                request_kind=request_kind,
                context=context,
            )
        )
    if len(events) != REPLAY_QUERY_COUNT:
        raise ValueError(f"Expected {REPLAY_QUERY_COUNT} events, found {len(events)}")
    return events
