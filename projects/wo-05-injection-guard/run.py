"""Run the 60-attack and 100-benign before/after benchmark."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.baseline import evaluate_unguarded
from src.guard import GuardedAgent
from src.models import attack_succeeded, score_profile
from src.report import write_results

PROJECT_DIR = Path(__file__).resolve().parent
ATTACKS_PATH = PROJECT_DIR / "data" / "attacks.json"
NORMAL_PATH = PROJECT_DIR / "data" / "normal_resumes.json"
RESULTS_DIR = PROJECT_DIR / "results"
BYPASS_ID = "METADATA-SCORE_TAMPER-01"


def load_json(path: Path) -> list[dict[str, Any]]:
    """Load one inspectable synthetic input set."""
    return json.loads(path.read_text(encoding="utf-8"))


def _group_stats(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    """Aggregate attack outcomes by family or attacker objective."""
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row[field]
        stats = groups.setdefault(name, {
            "count": 0, "baseline_success": 0, "guarded_success": 0, "classifier_alerts": 0
        })
        stats["count"] += 1
        stats["baseline_success"] += int(row["baseline_success"])
        stats["guarded_success"] += int(row["guarded_success"])
        stats["classifier_alerts"] += int(row["classifier_alert"])
    for stats in groups.values():
        stats["baseline_rate"] = stats["baseline_success"] / stats["count"]
        stats["guarded_rate"] = stats["guarded_success"] / stats["count"]
    return groups


def replay(attacks: list[dict[str, Any]], normals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare side effects, legacy bypass, final rules, and benign alerts."""
    agent = GuardedAgent()
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    bypass: dict[str, Any] = {}
    for record in attacks:
        legitimate_score = score_profile(record["resume_text"])
        baseline = evaluate_unguarded(record)
        guarded = agent.evaluate(record)
        old_guard = agent.evaluate(record, legacy_hint_bug=True)
        audits.extend(guarded["audit"])
        row = {
            "attack_id": record["attack_id"],
            "family": record["family"],
            "goal": record["goal"],
            "variant": record["variant"],
            "baseline_success": attack_succeeded(record["goal"], baseline, legitimate_score),
            "legacy_success": attack_succeeded(record["goal"], old_guard["tools"], legitimate_score),
            "guarded_success": attack_succeeded(record["goal"], guarded["tools"], legitimate_score),
            "classifier_alert": guarded["classifier_alert"],
            "blocked_rules": guarded["blocked_rules"],
            "legitimate_score": legitimate_score,
            "guarded_score": guarded["tools"].score,
            "mock_email_count": len(guarded["tools"].outbox),
            "mock_ats_write_count": len(guarded["tools"].ats_writes),
        }
        rows.append(row)
        if record["attack_id"] == BYPASS_ID:
            bypass = {
                "attack_id": BYPASS_ID,
                "legacy_score": old_guard["tools"].score,
                "guarded_score": guarded["tools"].score,
                "blocked_rules": guarded["blocked_rules"],
                "classifier_alert": guarded["classifier_alert"],
            }
    normal_rows = []
    for record in normals:
        result = agent.evaluate(record)
        audits.extend(result["audit"])
        normal_rows.append({
            "case_id": record["case_id"],
            "classifier_alert": result["classifier_alert"],
            "completed": result["tools"].score is not None and bool(result["tools"].published),
            "blocked_rules": result["blocked_rules"],
        })
    result = {
        "measurement_boundary": "Deterministic planner and mock tools; no live LLM, email, or ATS",
        "attack_count": len(rows),
        "normal_count": len(normal_rows),
        "baseline_success": sum(row["baseline_success"] for row in rows),
        "legacy_success": sum(row["legacy_success"] for row in rows),
        "guarded_success": sum(row["guarded_success"] for row in rows),
        "benign_flagged": sum(row["classifier_alert"] for row in normal_rows),
        "benign_completed": sum(row["completed"] for row in normal_rows),
        "attack_classifier_alerts": sum(row["classifier_alert"] for row in rows),
        "blocked_rule_counts": dict(Counter(
            event["rule"] for event in audits if event["blocked"]
        )),
        "attack_rows": rows,
        "normal_rows": normal_rows,
        "audit_events": audits,
        "bypass": bypass,
    }
    result["baseline_rate"] = result["baseline_success"] / len(rows)
    result["legacy_rate"] = result["legacy_success"] / len(rows)
    result["guarded_rate"] = result["guarded_success"] / len(rows)
    result["false_positive_rate"] = result["benign_flagged"] / len(normal_rows)
    result["by_family"] = _group_stats(rows, "family")
    result["by_goal"] = _group_stats(rows, "goal")
    return result


def main() -> None:
    """Load the committed fixtures and persist the complete replay evidence."""
    results = replay(load_json(ATTACKS_PATH), load_json(NORMAL_PATH))
    write_results(RESULTS_DIR, results)
    keys = (
        "attack_count", "normal_count", "baseline_success", "legacy_success",
        "guarded_success", "benign_flagged", "benign_completed", "bypass",
    )
    print(json.dumps({key: results[key] for key in keys}, indent=2))


if __name__ == "__main__":
    main()
