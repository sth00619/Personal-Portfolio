"""Run paired prompt generation, automated evaluation, and blinded judge scoring."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from src.dataset import DATA_PATH, SAMPLE_SEED, QAExample, load_examples, select_examples
from src.evaluation import score_all
from src.llm import (
    INPUT_USD_PER_MILLION,
    OUTPUT_USD_PER_MILLION,
    CostBudget,
    LLMClient,
    LLMSettings,
    new_http_client,
)
from src.prompts import (
    ANSWER_PROMPTS,
    PROMPT_HASH_VERSION,
    answer_user_message,
    judge_system_prompt,
    judge_user_message,
)
from src.scoring import score_answer


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
PREDICTIONS_PATH = RESULTS_DIR / "predictions.jsonl"
JUDGE_PATH = RESULTS_DIR / "judge_scores.jsonl"
RESULT_PATH = RESULTS_DIR / "experiment_results.json"
JUDGE_SUMMARY_PATH = RESULTS_DIR / "judge_summary.json"
POWER_PATH = RESULTS_DIR / "sample_size_power.csv"
JUDGE_SAMPLE_SIZE = 30
JUDGE_SAMPLE_PER_SEGMENT = JUDGE_SAMPLE_SIZE // 2
JUDGE_SEED = 20_073
GENERATION_BATCH_SIZE = 128
MAX_PROMPT_FINGERPRINT_LENGTH = 16
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", flags=re.DOTALL)


def sha256_file(path: Path) -> str:
    """Return a SHA-256 fingerprint without loading a file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_fingerprint(system: str) -> str:
    """Fingerprint the system instruction used for one prompt variant."""
    return hashlib.sha256(
        f"{PROMPT_HASH_VERSION}\n{system}".encode("utf-8")
    ).hexdigest()[:MAX_PROMPT_FINGERPRINT_LENGTH]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL records, ignoring only a malformed trailing partial line."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                continue
            raise
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record {index + 1} is not an object")
        records.append(value)
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append and flush one local checkpoint without storing credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        target.flush()
        os.fsync(target.fileno())


def current_prediction_map(
    records: list[dict[str, Any]], settings: LLMSettings, prompt_hashes: dict[str, str]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Keep latest response rows for the exact model and prompt fingerprints."""
    current: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        version = str(record.get("prompt_version", ""))
        if (
            record.get("model") == settings.model
            and record.get("provider") == settings.provider
            and record.get("base_url") == settings.base_url
            and record.get("max_tokens") == settings.max_tokens
            and version in prompt_hashes
            and record.get("prompt_hash") == prompt_hashes[version]
        ):
            current[(str(record["question_id"]), version)] = record
    return current


async def generate_one(
    example: QAExample,
    version: str,
    model: str,
    prompt_hash: str,
    client: LLMClient,
    semaphore: asyncio.Semaphore,
    write_lock: asyncio.Lock,
) -> dict[str, Any]:
    """Generate one response and append a resumable local record."""
    async with semaphore:
        completion = await client.complete(
            ANSWER_PROMPTS[version], answer_user_message(example), model=model
        )
    record: dict[str, Any] = {
        "question_id": example.question_id,
        "prompt_version": version,
        "prompt_hash": prompt_hash,
        "model": model,
        "provider": client.settings.provider,
        "base_url": client.settings.base_url,
        "max_tokens": client.settings.max_tokens,
        "prediction": completion.text,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
    }
    async with write_lock:
        append_jsonl(PREDICTIONS_PATH, record)
    return record


async def generate_answers(
    examples: list[QAExample], settings: LLMSettings, cost_budget: CostBudget
) -> dict[str, dict[str, str]]:
    """Generate A/B responses with bounded concurrency and restart-safe checkpoints."""
    prompt_hashes = {key: prompt_fingerprint(value) for key, value in ANSWER_PROMPTS.items()}
    completed = current_prediction_map(
        read_jsonl(PREDICTIONS_PATH), settings, prompt_hashes
    )
    pending = [
        (example, version)
        for example in examples
        for version in ("A", "B")
        if (example.question_id, version) not in completed
    ]
    print(
        f"Generation records: total={len(examples) * 2}, cached={len(completed)}, pending={len(pending)}",
        flush=True,
    )
    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(settings.concurrency)
    async with new_http_client() as http_client:
        api = LLMClient(settings, http_client, cost_budget)
        for offset in range(0, len(pending), GENERATION_BATCH_SIZE):
            batch = pending[offset:offset + GENERATION_BATCH_SIZE]
            results = await asyncio.gather(*[
                generate_one(
                    example, version, settings.model, prompt_hashes[version],
                    api, semaphore, write_lock,
                )
                for example, version in batch
            ], return_exceptions=True)
            failures = [item for item in results if isinstance(item, BaseException)]
            completed_count = offset + len(batch) - len(failures)
            print(
                f"Generation batch progress: {completed_count}/{len(pending)} new records; failures={len(failures)}",
                flush=True,
            )
            if failures:
                first = failures[0]
                raise RuntimeError(
                    f"{len(failures)} calls failed in the current batch ({type(first).__name__}); "
                    "successful rows are checkpointed. Fix endpoint/rate limits and rerun to resume."
                ) from first
    refreshed = current_prediction_map(
        read_jsonl(PREDICTIONS_PATH), settings, prompt_hashes
    )
    output = {"A": {}, "B": {}}
    for example in examples:
        for version in ("A", "B"):
            key = (example.question_id, version)
            if key not in refreshed:
                raise RuntimeError(f"Missing response for {example.question_id}/{version}")
            output[version][example.question_id] = str(refreshed[key]["prediction"])
    return output


def select_judge_sample(
    examples: list[QAExample], seed: int = JUDGE_SEED
) -> list[QAExample]:
    """Select a reproducible 15/15 answerable/unanswerable judge sample."""
    rng = np.random.default_rng(seed)
    selected: list[QAExample] = []
    for impossible in (False, True):
        segment = [example for example in examples if example.is_impossible == impossible]
        if len(segment) < JUDGE_SAMPLE_PER_SEGMENT:
            raise ValueError("The evaluation split cannot supply the balanced judge sample")
        positions = rng.choice(len(segment), size=JUDGE_SAMPLE_PER_SEGMENT, replace=False)
        selected.extend(segment[int(position)] for position in positions)
    return sorted(selected, key=lambda item: item.question_id)


def parse_judge_scores(text: str) -> tuple[int, int]:
    """Extract and validate two blinded integer scores from judge JSON."""
    match = JSON_OBJECT_PATTERN.search(text)
    if not match:
        raise ValueError("Judge did not return a JSON object")
    payload = json.loads(match.group(0))
    score_x, score_y = payload.get("score_x"), payload.get("score_y")
    if (
        not isinstance(score_x, int)
        or not isinstance(score_y, int)
        or isinstance(score_y, bool)
        or not 1 <= score_x <= 5
        or not 1 <= score_y <= 5
    ):
        raise ValueError("Judge scores must be integers from 1 to 5")
    return score_x, score_y


async def judge_one(
    example: QAExample,
    predictions: dict[str, dict[str, str]],
    settings: LLMSettings,
    api: LLMClient,
    semaphore: asyncio.Semaphore,
    write_lock: asyncio.Lock,
    swapped: bool,
    signature: str,
) -> dict[str, Any]:
    """Obtain one blinded paired judge score and checkpoint it locally."""
    candidate_x = predictions["B"][example.question_id] if swapped else predictions["A"][example.question_id]
    candidate_y = predictions["A"][example.question_id] if swapped else predictions["B"][example.question_id]
    async with semaphore:
        completion = await api.complete(
            judge_system_prompt(),
            judge_user_message(example, candidate_x, candidate_y),
            model=settings.judge_model,
        )
    score_x, score_y = parse_judge_scores(completion.text)
    score_a, score_b = (score_y, score_x) if swapped else (score_x, score_y)
    record = {
        "question_id": example.question_id,
        "is_impossible": example.is_impossible,
        "display_order_swapped": swapped,
        "score_a": score_a,
        "score_b": score_b,
        "judge_model": settings.judge_model,
        "experiment_fingerprint": signature,
        "max_tokens": settings.max_tokens,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
    }
    async with write_lock:
        append_jsonl(JUDGE_PATH, record)
    return record


async def score_judge_sample(
    examples: list[QAExample],
    predictions: dict[str, dict[str, str]],
    settings: LLMSettings,
    cost_budget: CostBudget,
) -> list[dict[str, Any]]:
    """Resume the stratified judge sample while randomizing candidate order."""
    sample = select_judge_sample(examples)
    signature = hashlib.sha256("|".join((
        settings.provider,
        settings.base_url,
        settings.model,
        settings.judge_model,
        str(settings.max_tokens),
        *(prompt_fingerprint(prompt) for prompt in ANSWER_PROMPTS.values()),
    )).encode("utf-8")).hexdigest()[:24]
    existing_records = read_jsonl(JUDGE_PATH)
    existing = {
        str(record["question_id"]): record
        for record in existing_records
        if record.get("experiment_fingerprint") == signature
    }
    pending = [example for example in sample if example.question_id not in existing]
    print(
        f"Judge records: total={len(sample)}, cached={len(sample) - len(pending)}, pending={len(pending)}",
        flush=True,
    )
    rng = np.random.default_rng(JUDGE_SEED)
    swaps = {example.question_id: bool(rng.integers(0, 2)) for example in sample}
    semaphore = asyncio.Semaphore(settings.concurrency)
    write_lock = asyncio.Lock()
    async with new_http_client() as http_client:
        api = LLMClient(settings, http_client, cost_budget)
        results = await asyncio.gather(*[
            judge_one(
                example, predictions, settings, api, semaphore, write_lock,
                swaps[example.question_id], signature,
            )
            for example in pending
        ], return_exceptions=True)
    failures = [item for item in results if isinstance(item, BaseException)]
    if failures:
        first = failures[0]
        raise RuntimeError(
            f"{len(failures)} judge calls failed ({type(first).__name__}); successful judgments are checkpointed"
        ) from first
    refreshed = {
        str(record["question_id"]): record
        for record in read_jsonl(JUDGE_PATH)
        if record.get("experiment_fingerprint") == signature
    }
    return [refreshed[example.question_id] for example in sample]


def cohen_kappa(left: list[str], right: list[str]) -> float | None:
    """Calculate unweighted Cohen's kappa for A/B/tie categorical choices."""
    if len(left) != len(right) or not left:
        raise ValueError("Cohen's kappa needs equally sized non-empty labels")
    categories = ("A", "B", "tie")
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    expected = sum(
        (left.count(category) / len(left)) * (right.count(category) / len(right))
        for category in categories
    )
    if expected == 1:
        return 1.0 if observed == 1 else None
    return float((observed - expected) / (1 - expected))


def summarize_judge(
    examples: list[QAExample],
    predictions: dict[str, dict[str, str]],
    judge_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare judge scores and pairwise preferences with automatic F1 scoring."""
    example_by_id = {example.question_id: example for example in examples}
    auto_choices: list[str] = []
    judge_choices: list[str] = []
    auto_f1: list[float] = []
    judge_scores: list[float] = []
    details: list[dict[str, Any]] = []
    for row in judge_rows:
        example = example_by_id[str(row["question_id"])]
        score_a = float(score_answer(
            predictions["A"][example.question_id], example.answers, example.is_impossible
        )["f1"])
        score_b = float(score_answer(
            predictions["B"][example.question_id], example.answers, example.is_impossible
        )["f1"])
        judge_a, judge_b = int(row["score_a"]), int(row["score_b"])
        auto_choice = "A" if score_a > score_b else "B" if score_b > score_a else "tie"
        judge_choice = "A" if judge_a > judge_b else "B" if judge_b > judge_a else "tie"
        auto_choices.append(auto_choice)
        judge_choices.append(judge_choice)
        auto_f1.extend((score_a, score_b))
        judge_scores.extend((float(judge_a), float(judge_b)))
        details.append({
            "question_id": example.question_id,
            "segment": "unanswerable" if example.is_impossible else "answerable",
            "auto_f1_a": score_a,
            "auto_f1_b": score_b,
            "judge_score_a": judge_a,
            "judge_score_b": judge_b,
            "auto_choice": auto_choice,
            "judge_choice": judge_choice,
        })
    correlation = spearmanr(auto_f1, judge_scores)
    means: dict[str, dict[str, float | int]] = {}
    for segment in ("all", "answerable", "unanswerable"):
        selected = details if segment == "all" else [row for row in details if row["segment"] == segment]
        means[segment] = {
            "n": len(selected),
            "mean_judge_score_a": float(np.mean([row["judge_score_a"] for row in selected])),
            "mean_judge_score_b": float(np.mean([row["judge_score_b"] for row in selected])),
        }
    return {
        "n": len(judge_rows),
        "sample_design": "15 answerable and 15 unanswerable rows; deterministic stratified sample",
        "judge_model": judge_rows[0]["judge_model"] if judge_rows else None,
        "mean_scores": means,
        "pairwise_winner_agreement_rate": float(
            np.mean(np.asarray(auto_choices) == np.asarray(judge_choices))
        ),
        "pairwise_winner_cohen_kappa": cohen_kappa(auto_choices, judge_choices),
        "spearman_rho_auto_f1_vs_judge_score": (
            float(correlation.statistic) if np.isfinite(correlation.statistic) else None
        ),
        "spearman_p_value_descriptive": (
            float(correlation.pvalue) if np.isfinite(correlation.pvalue) else None
        ),
        "details": details,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write a deterministic UTF-8 JSON report atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write power rows as LF-delimited CSV."""
    import csv

    if not rows:
        raise ValueError("Cannot write an empty result table")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


async def main() -> None:
    """Run prompt generation, automated scoring, and judge evaluation."""
    settings = LLMSettings.from_environment()
    cost_budget = CostBudget(
        RESULTS_DIR / "budget_reservations.json", settings.model, settings.cost_limit_usd
    )
    raw_examples = load_examples(DATA_PATH)
    sample_size = int(os.getenv("SAMPLE_SIZE", "300"))
    examples = select_examples(raw_examples, sample_size)
    segment_counts = {
        "answerable": sum(not example.is_impossible for example in examples),
        "unanswerable": sum(example.is_impossible for example in examples),
    }
    print(
        f"Evaluation set: n={len(examples)}, answerable={segment_counts['answerable']}, "
        f"unanswerable={segment_counts['unanswerable']}; model={settings.model}; "
        f"conservative_budget_reserved=${cost_budget.reserved_usd:.4f}/"
        f"${settings.cost_limit_usd:.2f}",
        flush=True,
    )
    predictions = await generate_answers(examples, settings, cost_budget)
    automatic = score_all(examples, predictions)
    judge_rows = await score_judge_sample(examples, predictions, settings, cost_budget)
    judge_summary = summarize_judge(examples, predictions, judge_rows)
    selected_ids = {example.question_id for example in examples}
    selected_records = [
        record for record in read_jsonl(PREDICTIONS_PATH)
        if str(record.get("question_id")) in selected_ids
        and record.get("model") == settings.model
        and record.get("provider") == settings.provider
        and record.get("base_url") == settings.base_url
        and record.get("max_tokens") == settings.max_tokens
    ]
    usage = {
        "generation_records": len(selected_records),
        "provider_prompt_tokens": int(sum(
            int(record["prompt_tokens"]) for record in selected_records
            if record.get("prompt_tokens") is not None
        )),
        "provider_completion_tokens": int(sum(
            int(record["completion_tokens"]) for record in selected_records
            if record.get("completion_tokens") is not None
        )),
        "judge_calls": len(judge_rows),
        "judge_prompt_tokens": int(sum(
            int(record["prompt_tokens"]) for record in judge_rows
            if record.get("prompt_tokens") is not None
        )),
        "judge_completion_tokens": int(sum(
            int(record["completion_tokens"]) for record in judge_rows
            if record.get("completion_tokens") is not None
        )),
    }
    total_prompt_tokens = usage["provider_prompt_tokens"] + usage["judge_prompt_tokens"]
    total_completion_tokens = usage["provider_completion_tokens"] + usage["judge_completion_tokens"]
    estimated_cost_usd = (
        total_prompt_tokens * INPUT_USD_PER_MILLION
        + total_completion_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    metadata = {
        "dataset": "SQuAD 2.0 dev",
        "dataset_url": "https://rajpurkar.github.io/SQuAD-explorer/",
        "dataset_sha256": sha256_file(DATA_PATH),
        "full_dev_rows": len(raw_examples),
        "evaluation_rows": len(examples),
        "segment_counts": segment_counts,
        "evaluation_design": (
            "entire official dev split" if len(examples) == len(raw_examples)
            else f"balanced stratified sample of {len(examples)} with seed {SAMPLE_SEED}"
        ),
        "answer_model": settings.model,
        "provider": settings.provider,
        "endpoint": settings.base_url,
        "judge_model": settings.judge_model,
        "prompts": {
            version: {"system": system, "sha256_prefix": prompt_fingerprint(system)}
            for version, system in ANSWER_PROMPTS.items()
        },
        "primary_metric": "paired F1 difference B minus A",
        "primary_test": "two-sided paired t-test; paired percentile bootstrap 95% CI",
        "bootstrap_repetitions": 2_000,
        "segment_test_correction": "Holm correction across answerable and unanswerable F1 comparisons",
        "sample_size_power": "post-hoc paired t-test power estimated by resampling observed F1 deltas; 2,000 repetitions",
        "usage": usage,
        "estimated_cost_usd_from_provider_token_usage": estimated_cost_usd,
        "conservative_budget_reserved_usd": cost_budget.reserved_usd,
        "conservative_budget_limit_usd": cost_budget.limit_usd,
    }
    result = {
        "metadata": metadata,
        "automatic_evaluation": automatic,
        "llm_as_judge": {key: value for key, value in judge_summary.items() if key != "details"},
    }
    write_json(RESULT_PATH, result)
    write_json(JUDGE_SUMMARY_PATH, judge_summary)
    write_csv(POWER_PATH, automatic["sample_size_power"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
