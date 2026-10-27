"""Run GSM8K and MMLU evaluations and write case-level evidence."""

from __future__ import annotations

import json
from pathlib import Path

from wo25.config import (
    ADAPTER_DIR, BASE_MODEL_REPO, BASE_MODEL_REVISION, FEW_SHOT_COUNTS,
    GENERATION_DIR, MODEL_MAX_TOKENS, MMLU_SUBJECTS, PROCESSED_DATA_DIR,
    QUANTIZATION_BITS, RAG_TOP_K_VALUES, RESULTS_DIR,
)
from wo25.data import _write_jsonl
from wo25.model import generate, load_model
from wo25.prompts import build_gsm_messages, build_mmlu_messages
from wo25.retrieval import WorkedExampleRetriever
from wo25.scoring import parse_gold_gsm8k, parse_gsm8k_answer, parse_mmlu_answer


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _gsm_run(method: str, test: list[dict], train: list[dict], model, tokenizer,
             few_shot: int = 0, top_k: int = 0,
             destination: Path | None = None) -> list[dict]:
    retriever = WorkedExampleRetriever(train) if method == "rag" else None
    existing = {}
    if destination and destination.exists():
        existing = {row["case_id"]: row for row in _read(destination)}
    rows: list[dict] = []
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
    stream = destination.open("a", encoding="utf-8") if destination else None
    for index, item in enumerate(test, start=1):
        if item["case_id"] in existing:
            rows.append(existing[item["case_id"]])
            continue
        demos = []
        if method == "few_shot":
            demos = train[:few_shot]
        elif method == "rag" and retriever:
            demos = retriever.retrieve(item["question"], top_k, {item["question"]})
        messages = build_gsm_messages(item["question"], method, demos)
        prediction = generate(model, tokenizer, messages, MODEL_MAX_TOKENS)
        predicted_value = parse_gsm8k_answer(prediction)
        gold_value = parse_gold_gsm8k(item["answer"])
        rows.append({
            "case_id": item["case_id"], "method": method, "question": item["question"],
            "gold_answer": gold_value, "prediction": prediction, "predicted_answer": predicted_value,
            "correct": predicted_value is not None and predicted_value == gold_value,
            "retrieved_case_ids": [row["case_id"] for row in demos],
        })
        if stream:
            stream.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
            stream.flush()
        if index % 100 == 0:
            print(f"{method}: {index}/{len(test)}", flush=True)
    if stream:
        stream.close()
    return rows


def score_validation_adapter(adapter_path: Path) -> dict:
    """Score a LoRA candidate on the fixed train-only validation subset."""
    validation = _read(PROCESSED_DATA_DIR / "gsm8k_validation.jsonl")
    model, tokenizer = load_model(adapter_path)
    rows = _gsm_run("lora", validation, [], model, tokenizer)
    correct = sum(row["correct"] for row in rows)
    return {"correct": correct, "total": len(rows), "accuracy_percent": 100 * correct / len(rows)}


def run_prompt_validation_sweeps() -> dict:
    """Compare few-shot counts and RAG top-k on the same held-out train examples."""
    validation = _read(PROCESSED_DATA_DIR / "gsm8k_validation.jsonl")
    train = _read(PROCESSED_DATA_DIR / "gsm8k_train_pool.jsonl")
    model, tokenizer = load_model()
    result: dict[str, dict] = {"few_shot": {}, "rag": {}}
    for count in FEW_SHOT_COUNTS:
        rows = _gsm_run("few_shot", validation, train, model, tokenizer, few_shot=count)
        correct = sum(row["correct"] for row in rows)
        result["few_shot"][str(count)] = {"correct": correct, "total": len(rows),
                                                "accuracy_percent": 100 * correct / len(rows)}
    for top_k in RAG_TOP_K_VALUES:
        rows = _gsm_run("rag", validation, train, model, tokenizer, top_k=top_k)
        correct = sum(row["correct"] for row in rows)
        result["rag"][str(top_k)] = {"correct": correct, "total": len(rows),
                                         "accuracy_percent": 100 * correct / len(rows)}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "prompt_validation_sweeps.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_gsm8k() -> dict:
    """Evaluate all four strategies on every official GSM8K test example."""
    test = _read(PROCESSED_DATA_DIR / "gsm8k_test.jsonl")
    train = _read(PROCESSED_DATA_DIR / "gsm8k_train_pool.jsonl")
    base, tokenizer = load_model()
    lora, lora_tokenizer = load_model(ADAPTER_DIR / "final" / "adapter")
    method_models = {"zero_shot": (base, tokenizer), "few_shot": (base, tokenizer),
                     "rag": (base, tokenizer), "lora": (lora, lora_tokenizer)}
    sweep_path = RESULTS_DIR / "prompt_validation_sweeps.json"
    prompt_sweeps = json.loads(sweep_path.read_text(encoding="utf-8")) if sweep_path.exists() else {}
    selected_few_shot = min(
        FEW_SHOT_COUNTS,
        key=lambda value: (-prompt_sweeps.get("few_shot", {}).get(str(value), {}).get("accuracy_percent", -1), value),
    )
    selected_top_k = min(
        RAG_TOP_K_VALUES,
        key=lambda value: (-prompt_sweeps.get("rag", {}).get(str(value), {}).get("accuracy_percent", -1), value),
    )
    scores = {}
    for method, (model, tok) in method_models.items():
        destination = GENERATION_DIR / f"gsm8k_{method}.jsonl"
        rows = _gsm_run(method, test, train, model, tok,
                        few_shot=selected_few_shot if method == "few_shot" else 0,
                        top_k=selected_top_k if method == "rag" else 0, destination=destination)
        _write_jsonl(destination.with_suffix(".ordered.jsonl"), rows)
        destination.with_suffix(".ordered.jsonl").replace(destination)
        correct = sum(row["correct"] for row in rows)
        scores[method] = {"correct": correct, "total": len(rows), "accuracy_percent": 100 * correct / len(rows)}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sweep_path = RESULTS_DIR / "lora_sweep_runs.json"
    sweep = json.loads(sweep_path.read_text(encoding="utf-8")) if sweep_path.exists() else {}
    result = {
        "dataset": "GSM8K official test",
        "base_model": {"repo_id": BASE_MODEL_REPO, "revision": BASE_MODEL_REVISION,
                       "quantization_bits": QUANTIZATION_BITS},
        "decoding": {"max_new_tokens": MODEL_MAX_TOKENS, "sampling": False},
        "selected_settings": {"few_shot_examples": selected_few_shot,
                              "rag_top_k": selected_top_k,
                              "lora": sweep.get("selected_candidate")},
        "scores": scores,
    }
    (RESULTS_DIR / "gsm8k_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def run_mmlu() -> dict:
    """Compare base and final LoRA on the identical balanced 100-item MMLU sample."""
    items = _read(PROCESSED_DATA_DIR / "mmlu_test_sample.jsonl")
    _, demos_by_subject = __import__("wo25.data", fromlist=["load_mmlu_sample"]).load_mmlu_sample()
    models = {"base": load_model(), "lora": load_model(ADAPTER_DIR / "final" / "adapter")}
    result: dict[str, dict] = {}
    for name, (model, tokenizer) in models.items():
        rows = []
        for index, item in enumerate(items, start=1):
            demos = demos_by_subject[item["subject"]][:5]
            prediction = generate(model, tokenizer, build_mmlu_messages(item, demos), 16)
            answer = parse_mmlu_answer(prediction)
            rows.append({"case_id": item["case_id"], "subject": item["subject"],
                         "gold": item["answer"], "prediction": prediction, "parsed": answer,
                         "correct": answer == item["answer"]})
            if index % 25 == 0:
                print(f"MMLU {name}: {index}/{len(items)}", flush=True)
        _write_jsonl(GENERATION_DIR / f"mmlu_{name}.jsonl", rows)
        correct = sum(row["correct"] for row in rows)
        result[name] = {"correct": correct, "total": len(rows), "accuracy_percent": 100 * correct / len(rows)}
    result["delta_percentage_points"] = round(result["lora"]["accuracy_percent"] - result["base"]["accuracy_percent"], 2)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "mmlu_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    print(json.dumps({"gsm8k": run_gsm8k(), "mmlu": run_mmlu()}, indent=2), flush=True)


if __name__ == "__main__":
    main()
