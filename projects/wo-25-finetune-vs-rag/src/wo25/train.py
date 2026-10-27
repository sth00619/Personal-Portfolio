"""Small controlled LoRA hyperparameter sweep and final adapter training."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from wo25.config import (
    ADAPTER_DIR, LORA_BATCH_SIZE, LORA_DROPOUT, LORA_FINAL_STEPS, LORA_LAYERS,
    LORA_LEARNING_RATE, LORA_MAX_SEQUENCE_LENGTH, LORA_RANK_VALUES,
    LORA_TRAIN_SAMPLE_SIZES, LORA_TUNE_STEPS, PROCESSED_DATA_DIR, RANDOM_SEED,
    RESULTS_DIR,
)
from wo25.data import _write_jsonl, save_training_jsonl


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _train(train_path: Path, valid_path: Path, adapter_path: Path, rank: int, iters: int) -> None:
    """Run MLX-LM LoRA against the same quantized base model."""
    from mlx_lm import lora

    import subprocess
    import sys

    model_path = adapter_path.parents[3] / "models/qwen2.5-1.5b-instruct-4bit"
    config_dir = adapter_path.parent / f".{adapter_path.name}-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "lora_config.yaml"
    config_path.write_text(
        "lora_parameters:\n  rank: %d\n  dropout: %.4f\n  scale: 20.0\n" % (rank, LORA_DROPOUT),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "-m", "mlx_lm", "lora", "--model", str(model_path), "--train",
         "--data", str(train_path.parent), "--adapter-path", str(adapter_path), "--config", str(config_path),
         "--iters", str(iters), "--batch-size", str(LORA_BATCH_SIZE), "--num-layers", str(LORA_LAYERS),
         "--learning-rate", str(LORA_LEARNING_RATE), "--max-seq-length", str(LORA_MAX_SEQUENCE_LENGTH),
         "--val-batches", "25", "--steps-per-report", "10", "--steps-per-eval", "50",
         "--save-every", str(iters), "--mask-prompt", "--seed", str(RANDOM_SEED)], check=True
    )


def run_sweep() -> None:
    """Compare rank and training volume using the same held-out validation set."""
    rows = _load_jsonl(PROCESSED_DATA_DIR / "gsm8k_train_pool.jsonl")
    random.Random(RANDOM_SEED).shuffle(rows)
    train_sizes = LORA_TRAIN_SAMPLE_SIZES
    ranks = LORA_RANK_VALUES
    experiments = [(4, 256), (4, 1024), (8, 1024)]
    results = []
    for rank, size in experiments:
        chosen = rows[:size]
        run_dir = ADAPTER_DIR / f"sweep-r{rank}-n{size}"
        train_file = run_dir / "train" / "train.jsonl"
        valid_file = run_dir / "train" / "valid.jsonl"
        save_training_jsonl(chosen, train_file)
        validation = _load_jsonl(PROCESSED_DATA_DIR / "gsm8k_validation.jsonl")
        save_training_jsonl(validation, valid_file)
        _train(train_file, valid_file, run_dir / "adapter", rank, LORA_TUNE_STEPS)
        from wo25.evaluate import score_validation_adapter
        validation_score = score_validation_adapter(run_dir / "adapter")
        results.append({"rank": rank, "training_examples": size, "steps": LORA_TUNE_STEPS,
                        "validation_file": str(valid_file), "adapter": str(run_dir / "adapter"),
                        "validation": validation_score})
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "lora_sweep_runs.json").write_text(json.dumps({"candidates": {
        "rank": list(ranks), "training_examples": list(train_sizes)}, "runs": results}, indent=2) + "\n")

    # Select by held-out accuracy; ties prefer lower rank then fewer examples.
    best = sorted(results, key=lambda row: (-row["validation"]["accuracy_percent"],
                                             row["rank"], row["training_examples"]))[0]
    final_dir = ADAPTER_DIR / "final"
    final_adapter = final_dir / "adapter"
    if final_adapter.exists():
        shutil.rmtree(final_adapter)
    final_train = final_dir / "train" / "train.jsonl"
    final_valid = final_dir / "train" / "valid.jsonl"
    save_training_jsonl(rows[:best["training_examples"]], final_train)
    validation = _load_jsonl(PROCESSED_DATA_DIR / "gsm8k_validation.jsonl")
    save_training_jsonl(validation, final_valid)
    _train(final_train, final_valid, final_adapter, rank=best["rank"], iters=LORA_FINAL_STEPS)
    from wo25.evaluate import run_prompt_validation_sweeps
    prompt_sweeps = run_prompt_validation_sweeps()
    (RESULTS_DIR / "lora_sweep_runs.json").write_text(json.dumps({"candidates": {
        "rank": list(ranks), "training_examples": list(train_sizes)}, "runs": results,
        "selected_candidate": best, "final_adapter_steps": LORA_FINAL_STEPS,
        "prompt_sweeps": prompt_sweeps}, indent=2) + "\n")


if __name__ == "__main__":
    run_sweep()
