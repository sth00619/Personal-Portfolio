"""Summarize saved case-level results and select evidence examples."""

from __future__ import annotations

import json
from pathlib import Path

from wo25.config import GENERATION_DIR, GSM8K_TEST_SIZE, RESULTS_DIR


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def summarize() -> dict:
    """Recompute count/denominator accuracy and method-specific case groups."""
    methods = ("zero_shot", "few_shot", "rag", "lora")
    rows = {method: read_jsonl(GENERATION_DIR / f"gsm8k_{method}.jsonl") for method in methods}
    ids = [{row["case_id"] for row in rows[method]} for method in methods]
    if any(len(rows[method]) != GSM8K_TEST_SIZE for method in methods):
        counts = {method: len(rows[method]) for method in methods}
        raise ValueError(f"Expected {GSM8K_TEST_SIZE} official test rows per method; found {counts}")
    if any(case_ids != ids[0] for case_ids in ids[1:]):
        raise ValueError("GSM8K method files do not contain the same case IDs")
    case_order = [row["case_id"] for row in rows["zero_shot"]]
    scores = {method: {"correct": sum(row["correct"] for row in rows[method]),
                       "total": len(rows[method]),
                       "accuracy_percent": 100 * sum(row["correct"] for row in rows[method]) / len(rows[method])}
              for method in methods}
    by_method = {method: {row["case_id"]: row for row in rows[method]} for method in methods}
    wrong_all = [case_id for case_id in case_order if not any(by_method[m][case_id]["correct"] for m in methods)]
    rag_only = [case_id for case_id in case_order if by_method["rag"][case_id]["correct"] and
                not any(by_method[m][case_id]["correct"] for m in methods if m != "rag")]
    lora_only = [case_id for case_id in case_order if by_method["lora"][case_id]["correct"] and
                 not any(by_method[m][case_id]["correct"] for m in methods if m != "lora")]
    examples = {"all_wrong": wrong_all[:3], "rag_only": rag_only[:3], "lora_only": lora_only[:3]}
    selected_rows = {
        group: [
            {"case_id": case_id, "question": by_method["zero_shot"][case_id]["question"],
             "gold_answer": by_method["zero_shot"][case_id]["gold_answer"],
             "methods": {method: {"correct": by_method[method][case_id]["correct"],
                                  "predicted_answer": by_method[method][case_id]["predicted_answer"],
                                  "prediction": by_method[method][case_id]["prediction"],
                                  "retrieved_case_ids": by_method[method][case_id]["retrieved_case_ids"]}
                         for method in methods}}
            for case_id in case_ids
        ]
        for group, case_ids in examples.items()
    }
    result = {"scores": scores, "disjoint_case_groups": {key: len(value) for key, value in
              {"all_wrong": wrong_all, "rag_only": rag_only, "lora_only": lora_only}.items()},
              "selected_case_ids": examples, "selected_examples_with_outputs": selected_rows}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "gsm8k_analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
