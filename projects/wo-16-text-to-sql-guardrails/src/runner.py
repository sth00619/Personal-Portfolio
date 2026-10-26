"""Run local-model generation and execution-accuracy evaluation."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from functools import lru_cache
import random
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
import mlx.core as mx
from mlx_lm import generate, load

from guardrails import execute_sql, explain_warnings, validate_schema, validate_sql

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
SEED = 1607
SUBSET_SIZE = 200
DEFAULT_MAX_TOKENS = 256
AUDIT_ANCHORS = {46, 62, 92}
_GOLD_CACHE: dict[tuple[str, str], list[tuple[Any, ...]] | str] = {}


def load_examples() -> list[dict[str, Any]]:
    """Read official Mini-Dev examples and select 200 deterministically by difficulty."""
    source = DATA_DIR / "mini_dev_sqlite.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("mini_dev_sqlite", "data", "train"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError(f"Unsupported dataset structure: {type(payload).__name__}")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload:
        groups[str(row.get("difficulty", "unknown")).lower()].append(row)
    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    names = sorted(groups)
    counts = {name: SUBSET_SIZE // len(names) for name in names}
    for name in names[: SUBSET_SIZE % len(names)]:
        counts[name] += 1
    for name in names:
        rng.shuffle(groups[name])
        selected.extend(groups[name][:counts[name]])
    anchor_rows = {int(row["question_id"]): row for row in payload
                   if int(row.get("question_id", -1)) in AUDIT_ANCHORS}
    selected_ids = {int(row["question_id"]) for row in selected}
    for anchor_id, anchor in anchor_rows.items():
        if anchor_id in selected_ids:
            continue
        replacements = [i for i, row in enumerate(selected)
                        if row["difficulty"] == anchor["difficulty"]
                        and int(row["question_id"]) not in AUDIT_ANCHORS]
        if not replacements:
            raise ValueError(f"Cannot preserve difficulty quota for audit case {anchor_id}")
        removed = selected[replacements[-1]]
        selected_ids.remove(int(removed["question_id"]))
        selected[replacements[-1]] = anchor
        selected_ids.add(anchor_id)
    selected.sort(key=lambda row: (str(row.get("db_id", "")), str(row.get("question", ""))))
    return selected


@lru_cache(maxsize=32)
def database_path(db_id: str) -> Path:
    """Find a database file from the extracted official archive."""
    candidates = list(DATA_DIR.rglob("*.sqlite")) + list(DATA_DIR.rglob("*.db"))
    exact = [path for path in candidates if path.parent.name == db_id]
    if exact:
        return exact[0]
    for path in candidates:
        if db_id.lower() in str(path.parent).lower():
            return path
    raise FileNotFoundError(f"No SQLite database found for db_id={db_id}")


def schema_text(database: Path) -> str:
    """Serialize database tables and columns for the model context."""
    with closing(sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)) as conn:
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return "\n".join(f"{name}: {ddl or '(no DDL)'}" for name, ddl in tables)


def prompt_for(example: dict[str, Any], schema: str, improved: bool) -> str:
    """Build baseline or revised prompt with explicit schema grounding."""
    question = example.get("question", "")
    evidence = example.get("evidence", "")
    shared = f"Database schema:\n{schema}\n\nQuestion: {question}\n"
    if evidence:
        shared += f"Benchmark evidence: {evidence}\n"
    if improved:
        instruction = (
            "Identify only tables and columns that appear in the schema. Map each phrase in the "
            "question to those fields, preserve requested aggregation and ordering, use the supplied "
            "evidence, and check every join key. Return exactly one executable SQLite SELECT query; "
            "no markdown, explanation, or write operation."
        )
    else:
        instruction = "Write a SQLite query that answers the question. Return only SQL."
    return f"{instruction}\n\n{shared}SQL:"


def extract_sql(output: str) -> str:
    """Remove common model wrappers without silently repairing SQL semantics."""
    text = output.strip()
    text = re.sub(r"^```(?:sql)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    match = re.search(r"(?is)\b(SELECT|WITH)\b.*", text)
    if match:
        text = match.group(0).strip()
    return text


def model_generate(model: Any, tokenizer: Any, prompt: str, max_tokens: int) -> str:
    """Generate one SQL candidate using deterministic chat-template decoding."""
    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    return generate(model, tokenizer, prompt=formatted, max_tokens=max_tokens,
                    sampler=lambda logits: mx.argmax(logits, axis=-1),
                    verbose=False)


def canonical_rows(rows: list[tuple[Any, ...]]) -> set[tuple[Any, ...]]:
    """Normalize and compare rows using the official unordered Mini-Dev EX rule."""
    def normalize(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 2)
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        return value
    return {tuple(normalize(value) for value in row) for row in rows}


def evaluate_sql(db: Path, gold: str, candidate: str, guarded: bool) -> dict[str, Any]:
    """Compare read-only SQL result bags and retain safety diagnostic details."""
    cache_key = (str(db.resolve()), gold)
    if cache_key not in _GOLD_CACHE:
        try:
            cached_rows, _ = execute_sql(db, gold)
            _GOLD_CACHE[cache_key] = cached_rows
        except sqlite3.Error as exc:
            _GOLD_CACHE[cache_key] = f"gold_execution_error: {str(exc)[:300]}"
    cached_gold = _GOLD_CACHE[cache_key]
    if isinstance(cached_gold, str):
        return {"correct": False, "executed": False, "blocked": False,
                "gold_executable": False, "reasons": [cached_gold], "warnings": []}
    gold_rows = cached_gold
    candidate_input = candidate
    guard = validate_sql(candidate) if guarded else None
    if guard and not guard.accepted:
        return {"correct": False, "executed": False, "blocked": True,
                "gold_executable": True,
                "reasons": list(guard.reasons), "warnings": []}
    if guard:
        candidate_input = guard.sql or ""
    try:
        if guarded:
            validate_schema(db, candidate_input)
        rows, _ = execute_sql(db, candidate_input)
        query_warnings = list(guard.warnings if guard else ())
        try:
            query_warnings.extend(explain_warnings(db, candidate_input))
        except sqlite3.Error:
            pass
        return {"correct": canonical_rows(rows) == canonical_rows(gold_rows),
                "executed": True, "blocked": False, "gold_executable": True,
                "reasons": [],
                "warnings": sorted(set(query_warnings)), "row_count": len(rows)}
    except sqlite3.Error as exc:
        return {"correct": False, "executed": False, "blocked": False,
                "gold_executable": True,
                "reasons": [f"execution_error: {str(exc)[:300]}"],
                "warnings": list(guard.warnings if guard else ())}


def main() -> None:
    """Generate, evaluate, and persist model outputs for the fixed subset."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mlx-community/Qwen2.5-Coder-3B-Instruct-4bit")
    parser.add_argument("--model-revision", default="3dd939c621c08e5753d5b89f35a2642cd83b98ca")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--limit", type=int, default=SUBSET_SIZE,
                        help="Use a smaller number only for a smoke run; final results use 200.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)
    examples = load_examples()[:args.limit]
    output_path = ARTIFACTS / "evaluation.jsonl"
    completed: dict[str, dict[str, Any]] = {}
    if args.resume and output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            completed[item["case_id"]] = item
    model_path = snapshot_download(repo_id=args.model, revision=args.model_revision)
    model, tokenizer = load(model_path)
    started = time.monotonic()
    for index, example in enumerate(examples, 1):
        case_id = str(example.get("question_id", example.get("id", index)))
        if case_id in completed and all(k in completed[case_id] for k in
                ("baseline", "baseline_guarded", "improved_guarded")):
            continue
        db_id = str(example["db_id"])
        database = database_path(db_id)
        schema = schema_text(database)
        gold = str(example.get("SQL", example.get("sql", "")))
        base_prompt = prompt_for(example, schema, False)
        improved_prompt = prompt_for(example, schema, True)
        base_sql = extract_sql(model_generate(model, tokenizer, base_prompt, args.max_tokens))
        improved_sql = extract_sql(model_generate(model, tokenizer, improved_prompt, args.max_tokens))
        row = {"case_id": case_id, "db_id": db_id,
               "difficulty": str(example.get("difficulty", "unknown")).lower(),
               "question": str(example.get("question", "")),
               "evidence": str(example.get("evidence", "")), "gold_sql": gold,
               "baseline_sql": base_sql, "improved_sql": improved_sql,
               "max_new_tokens": args.max_tokens, "decoding": "greedy",
               "baseline": evaluate_sql(database, gold, base_sql, False),
               "baseline_guarded": evaluate_sql(database, gold, base_sql, True),
               "improved_guarded": evaluate_sql(database, gold, improved_sql, True)}
        completed[case_id] = row
        with output_path.open("w", encoding="utf-8") as target:
            for value in completed.values():
                target.write(json.dumps(value, ensure_ascii=False) + "\n")
        if index == 1 or index % 10 == 0:
            print(f"[{index}/{len(examples)}] {case_id} {db_id}; elapsed={time.monotonic()-started:.1f}s",
                  flush=True)
    subprocess.run([sys.executable, str(ROOT / "src" / "score.py")], check=True)


if __name__ == "__main__":
    main()
