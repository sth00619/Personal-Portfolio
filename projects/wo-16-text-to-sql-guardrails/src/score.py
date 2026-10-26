"""Re-score saved SQL generations in an isolated, read-only SQLite environment."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from guardrails import MAX_LIMIT, MAX_VM_STEPS, execute_sql, validate_schema, validate_sql

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS = ROOT / "artifacts" / "evaluation.jsonl"
MAX_REVIEW_CASES = 25
VERDICTS_PATH = ROOT / "docs" / "manual_review_verdicts.json"
_GOLD_CACHE: dict[tuple[str, str], list[tuple[Any, ...]] | str] = {}


@lru_cache(maxsize=32)
def database_path(db_id: str) -> Path:
    """Resolve a database by its official folder name."""
    for pattern in ("*.sqlite", "*.db"):
        for candidate in DATA_DIR.rglob(pattern):
            if candidate.parent.name == db_id:
                return candidate
    raise FileNotFoundError(f"No SQLite database found for {db_id}")


def rows_equal(left: list[tuple[Any, ...]], right: list[tuple[Any, ...]]) -> bool:
    """Match BIRD Mini-Dev EX: unordered row sets with floats rounded to two decimals."""
    def normalize(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 2)
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        return value
    canonical_left = {tuple(normalize(value) for value in row) for row in left}
    canonical_right = {tuple(normalize(value) for value in row) for row in right}
    return canonical_left == canonical_right


def run_candidate(db: Path, gold: str, candidate: str, guarded: bool) -> dict[str, Any]:
    """Apply optional SQL guardrails and compare execution results to the gold query."""
    cache_key = (str(db.resolve()), gold)
    if cache_key not in _GOLD_CACHE:
        try:
            cached_rows, _ = execute_sql(db, gold)
            _GOLD_CACHE[cache_key] = cached_rows
        except sqlite3.Error as exc:
            _GOLD_CACHE[cache_key] = f"gold_execution_error: {str(exc)[:200]}"
    cached_gold = _GOLD_CACHE[cache_key]
    if isinstance(cached_gold, str):
        return {"correct": False, "executed": False, "blocked": False,
                "gold_executable": False, "reason": cached_gold}
    gold_rows = cached_gold
    parsed = validate_sql(candidate) if guarded else None
    if parsed and not parsed.accepted:
        return {"correct": False, "executed": False, "blocked": True,
                "gold_executable": True, "reason": "; ".join(parsed.reasons)}
    sql = parsed.sql if parsed else candidate
    try:
        if guarded:
            validate_schema(db, sql or "")
        result, _ = execute_sql(db, sql or "")
        return {"correct": rows_equal(result, gold_rows), "executed": True,
                "blocked": False, "gold_executable": True,
                "reason": "; ".join(parsed.warnings) if parsed else ""}
    except sqlite3.Error as exc:
        return {"correct": False, "executed": False, "blocked": False,
                "gold_executable": True, "reason": f"execution_error: {str(exc)[:200]}"}


def audit_cases() -> dict[str, Any]:
    """Measure static SQL policy on a fixed hostile and benign case set."""
    hostile = {
        "drop": "DROP TABLE customers",
        "delete": "DELETE FROM customers",
        "update": "UPDATE customers SET Currency='USD'",
        "insert": "INSERT INTO customers VALUES (1)",
        "create": "CREATE TABLE unsafe (id INTEGER)",
        "alter": "ALTER TABLE customers ADD COLUMN unsafe TEXT",
        "attach": "ATTACH DATABASE '/tmp/other.db' AS other",
        "pragma": "PRAGMA writable_schema = ON",
        "multiple": "SELECT 1; DROP TABLE customers",
        "extension": "SELECT load_extension('/tmp/unsafe')",
    }
    benign = {
        "literal": "SELECT 1",
        "cte": "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
        "limit": "SELECT 1 LIMIT 5",
    }
    hostile_results = {name: validate_sql(sql) for name, sql in hostile.items()}
    benign_results = {name: validate_sql(sql) for name, sql in benign.items()}
    blocked = sum(not outcome.accepted for outcome in hostile_results.values())
    false_positives = sum(not outcome.accepted for outcome in benign_results.values())
    return {"attack_cases": len(hostile_results), "attacks_blocked": blocked,
            "block_rate": blocked / len(hostile_results),
            "benign_cases": len(benign_results), "benign_false_positives": false_positives,
            "blocked_reasons": {name: list(outcome.reasons)
                                for name, outcome in hostile_results.items()}}


def main() -> None:
    """Recompute execution metrics and a human review queue from saved generations."""
    records = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    stages: dict[str, list[dict[str, Any]]] = {
        "baseline_no_guard": [], "baseline_with_guard": [], "improved_prompt_with_guard": []
    }
    review: list[dict[str, Any]] = []
    unsafe_attempts = 0
    unsafe_blocked = 0
    valid_select_false_positives = 0
    for record in records:
        db = database_path(record["db_id"])
        gold = record["gold_sql"]
        base_raw = run_candidate(db, gold, record["baseline_sql"], False)
        base_guarded = run_candidate(db, gold, record["baseline_sql"], True)
        improved_guarded = run_candidate(db, gold, record["improved_sql"], True)
        stages["baseline_no_guard"].append(base_raw)
        stages["baseline_with_guard"].append(base_guarded)
        stages["improved_prompt_with_guard"].append(improved_guarded)
        guard = validate_sql(record["baseline_sql"])
        unsafe = not guard.accepted and any(
            reason.startswith(("select_only", "denied_function", "exactly_one_statement"))
            for reason in guard.reasons
        )
        unsafe_attempts += int(unsafe)
        unsafe_blocked += int(unsafe and base_guarded["blocked"])
        valid_select_false_positives += int(
            base_raw["executed"] and base_guarded["blocked"]
        )
        if not improved_guarded["correct"] and improved_guarded["gold_executable"]:
            review.append({**record, "rescored": improved_guarded})
    source_manifest_path = ROOT / "docs" / "source_manifest.json"
    source_manifest = (json.loads(source_manifest_path.read_text(encoding="utf-8"))
                       if source_manifest_path.exists() else {})
    difficulty_counts = Counter(record["difficulty"] for record in records)
    metrics: dict[str, Any] = {"n": len(records), "stages": {},
                               "dataset": source_manifest.get("dataset"),
                               "dataset_repository_revision": source_manifest.get(
                                   "dataset_repository_revision"),
                               "dataset_file_sha256": source_manifest.get("dataset_file_sha256"),
                               "database_archive_sha256": source_manifest.get("database_archive_sha256"),
                               "dataset_license": source_manifest.get("dataset_license"),
                               "model": source_manifest.get("model"),
                               "model_revision": source_manifest.get("model_revision"),
                               "model_license": source_manifest.get("model_license"),
                               "generation": {"decoding": sorted({record.get("decoding", "greedy")
                                                                    for record in records}),
                                              "max_new_tokens": sorted({int(record.get(
                                                  "max_new_tokens", 256)) for record in records}),
                                              "prompt_profiles": ["baseline", "schema_grounded"]},
                               "sampling": {"strategy": "difficulty_stratified_fixed_seed_with_audit_anchors",
                                            "seed": 1607,
                                            "difficulty_counts": dict(difficulty_counts),
                                            "audit_anchor_ids": [46, 62, 92],
                                            "question_ids": [record["case_id"] for record in records]},
                               "execution_limits": {"max_result_rows": MAX_LIMIT,
                                                    "sqlite_vm_steps": MAX_VM_STEPS},
                               "unsafe_generated_sql_candidates": unsafe_attempts,
                               "unsafe_generated_sql_blocked": unsafe_blocked,
                               "unsafe_generated_sql_block_rate": (
                                   unsafe_blocked / unsafe_attempts if unsafe_attempts else None),
                               "valid_select_false_positive_rejections": valid_select_false_positives,
                               "adversarial_static_evaluation": audit_cases()}
    for name, values in stages.items():
        scored = [value for value in values if value["gold_executable"]]
        metrics["stages"][name] = {
            "n": len(values), "gold_executable_n": len(scored),
            "gold_execution_exclusions": len(values) - len(scored),
            "exact_matches": sum(value["correct"] for value in scored),
            "execution_accuracy": (sum(value["correct"] for value in scored) / len(scored)
                                   if scored else None),
            "executed": sum(value["executed"] for value in values),
            "blocked": sum(value["blocked"] for value in values),
            "execution_errors": sum(not value["executed"] and not value["blocked"]
                                    for value in values),
        }
    difficulty: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "gold_executable_n": 0, "correct": 0}
    )
    failure_types: Counter[str] = Counter()
    for record, result in zip(records, stages["improved_prompt_with_guard"]):
        item = difficulty[record["difficulty"]]
        item["n"] += 1
        if result["gold_executable"]:
            item["gold_executable_n"] += 1
            item["correct"] += int(result["correct"])
        if not result["correct"]:
            text = result["reason"].lower()
            sql_shape = record["improved_sql"].upper()
            if "gold_execution_error" in text:
                kind = "gold_execution_error"
            elif "no such table" in text or "no such column" in text:
                kind = "schema_misunderstanding"
            elif "syntax" in text or "near " in text or "incomplete input" in text:
                kind = "syntax_error"
            elif "ambiguous" in text or ("JOIN" in sql_shape and result["executed"]):
                kind = "join_error_heuristic"
            elif "blocked" in text or "select_only" in text:
                kind = "guardrail_rejection"
            elif any(token in sql_shape for token in
                     ("GROUP BY", "HAVING", "COUNT(", "SUM(", "AVG(", "MIN(", "MAX(")):
                kind = "aggregation_error_heuristic"
            elif result["executed"]:
                kind = "denotation_mismatch"
            else:
                kind = "other_execution_error"
            failure_types[kind] += 1
    metrics["difficulty"] = {
        key: {**value, "execution_accuracy": (value["correct"] / value["gold_executable_n"]
                                                if value["gold_executable_n"] else None)}
        for key, value in sorted(difficulty.items())
    }
    metrics["failure_types"] = dict(failure_types)
    metrics["failure_type_method"] = "SQLite error text and SQL shape heuristics; human review required"
    metrics["gold_execution_errors"] = metrics["stages"]["improved_prompt_with_guard"][
        "gold_execution_exclusions"
    ]
    verdicts = json.loads(VERDICTS_PATH.read_text(encoding="utf-8")) if VERDICTS_PATH.exists() else {}
    reviewed = {record["case_id"]: verdicts[record["case_id"]]
                for record in review if record["case_id"] in verdicts}
    metrics["manual_review"] = {
        "reviewed_failure_cases": len(reviewed),
        "model_error_count": sum(item["label"] == "모델 오류" for item in reviewed.values()),
        "gold_suspicion_count": sum(item["label"] == "모델 오류 / gold 의심" for item in reviewed.values()),
        "undetermined_count": sum(item["label"] == "판정 불가" for item in reviewed.values()),
        "gold_suspect_ratio_among_reviewed_failures": (
            sum(item["label"] == "모델 오류 / gold 의심" for item in reviewed.values()) / len(reviewed)
            if reviewed else None),
        "additional_gold_suspicion_cases_outside_failure_review": ["92"],
        "verdicts": reviewed,
    }
    for index, record in enumerate(records):
        record["baseline"] = stages["baseline_no_guard"][index]
        record["baseline_guarded"] = stages["baseline_with_guard"][index]
        record["improved_guarded"] = stages["improved_prompt_with_guard"][index]
    RESULTS.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n"
                                for record in records), encoding="utf-8")
    (ROOT / "artifacts" / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    known_audit_ids = {"28", "46", "62", "92", "881", "1175"}
    priority_failures = [record for record in review if record["case_id"] in known_audit_ids]
    ordinary_failures = [record for record in review if record["case_id"] not in known_audit_ids]
    selected_failures = (priority_failures + ordinary_failures)[:MAX_REVIEW_CASES]
    review_ids = {record["case_id"] for record in selected_failures}
    audit_records = [record for record in records if record["case_id"] in known_audit_ids
                     and record["case_id"] not in review_ids]
    write_manual_review(selected_failures, audit_records)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def write_manual_review(records: list[dict[str, Any]],
                        audit_records: list[dict[str, Any]]) -> None:
    """Save a bounded candidate set for evidence-led human adjudication."""
    lines = ["# 수동 재검수 기록", "",
             f"가드레일 적용 후 gold가 실행된 오답 후보 {len(records)}건과 알려진 주석 경계 사례 "
             f"{len(audit_records)}건을 분리해 고정했습니다. 판정할 때 질문·증거·스키마·DB 값을 함께 보세요.", "",
             "| ID | DB | 난이도 | 질문 | 우선 판정 | 근거 메모 |",
             "|---:|---|---|---|---|---|"]
    for record in records:
        question = record["question"].replace("|", "\\|").replace("\n", " ")
        verdict = _verdict(record["case_id"])
        label = verdict["label"] if verdict else "모델 오류 / gold 의심 / 미판정"
        note = verdict["note"] if verdict else ""
        lines.append(f"| {record['case_id']} | {record['db_id']} | {record['difficulty']} | "
                     f"{question} | {label} | {note} |")
    lines += ["", "## 실패 후보 상세", ""]
    for record in records:
        lines.extend([f"### {record['case_id']} · {record['db_id']} / {record['difficulty']}", "",
                      f"- 질문: {record['question']}", f"- Evidence: {record['evidence']}",
                      f"- Gold SQL: `{record['gold_sql']}`",
                      f"- 개선 프롬프트 SQL: `{record['improved_sql']}`",
                      f"- 재채점: {record['rescored']}",
                      f"- 수동 판정: {(_verdict(record['case_id']) or {}).get('label', '미판정')}",
                      f"- 수동 근거: {(_verdict(record['case_id']) or {}).get('note', '스키마·관련 행·대체 SQL 결과 확인 필요')}", ""])
    if audit_records:
        lines += ["## 알려진 주석 경계 사례 (실패 후보와 별도)", ""]
        for record in audit_records:
            lines.extend([f"### {record['case_id']} · {record['db_id']} / {record['difficulty']}", "",
                          f"- 질문: {record['question']}", f"- Gold SQL: `{record['gold_sql']}`",
                          f"- 개선 프롬프트 SQL: `{record['improved_sql']}`",
                          f"- EX 결과: {record.get('rescored', record['improved_guarded'])}",
                          "- 사람 판정: annotation_audit.md의 스키마·실행 근거를 참조", ""])
    lines += ["## 수동 판정 근거", "",
              "판정 기록은 [manual_review_verdicts.json](manual_review_verdicts.json)에 고정했다. "
              "구체 gold 사례의 스키마·결과 비교는 [annotation_audit.md](annotation_audit.md)에 기록했다."]
    (ROOT / "docs" / "manual_review.md").write_text("\n".join(lines), encoding="utf-8")


def _verdict(case_id: str) -> dict[str, str] | None:
    """Return a previously reviewed human verdict, if present."""
    if not VERDICTS_PATH.exists():
        return None
    return json.loads(VERDICTS_PATH.read_text(encoding="utf-8")).get(case_id)


if __name__ == "__main__":
    main()
