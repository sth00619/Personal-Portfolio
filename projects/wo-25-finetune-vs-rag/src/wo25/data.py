"""Fetch pinned GSM8K/MMLU files and create leakage-safe local splits."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_download

from wo25.config import (
    DATA_CACHE_DIR,
    DATASET_LICENSE,
    GSM8K_REPO,
    GSM8K_REVISION,
    GSM8K_TEST_FILE,
    GSM8K_TEST_SIZE,
    GSM8K_TRAIN_FILE,
    GSM8K_TRAIN_SIZE,
    MMLU_DEV_FILE,
    MMLU_PER_SUBJECT,
    MMLU_REPO,
    MMLU_REVISION,
    MMLU_SAMPLE_SIZE,
    MMLU_SUBJECTS,
    MMLU_TEST_FILE,
    MODEL_LICENSE,
    BASE_MODEL_REPO,
    BASE_MODEL_REVISION,
    PROCESSED_DATA_DIR,
    RANDOM_SEED,
    RAW_DATA_DIR,
    VALIDATION_SIZE,
    RESULTS_DIR,
)


def sha256_file(path: Path) -> str:
    """Return the hexadecimal SHA-256 checksum of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_dataset_file(repo_id: str, revision: str, filename: str) -> Path:
    """Download one pinned file into an ignored local raw-data directory."""
    destination = RAW_DATA_DIR / repo_id.replace("/", "--")
    destination.mkdir(parents=True, exist_ok=True)
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            revision=revision,
            local_dir=destination,
        )
    )


def _read_parquet(path: Path) -> pd.DataFrame:
    """Read a benchmark parquet file into a DataFrame."""
    return pd.read_parquet(path)


def split_gsm8k() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Load full official train/test splits and hold out validation from train only."""
    train_path = fetch_dataset_file(GSM8K_REPO, GSM8K_REVISION, GSM8K_TRAIN_FILE)
    test_path = fetch_dataset_file(GSM8K_REPO, GSM8K_REVISION, GSM8K_TEST_FILE)
    train_frame = _read_parquet(train_path)
    test_frame = _read_parquet(test_path)
    if len(train_frame) != GSM8K_TRAIN_SIZE or len(test_frame) != GSM8K_TEST_SIZE:
        raise ValueError(
            f"Unexpected GSM8K split sizes: train={len(train_frame)}, test={len(test_frame)}"
        )
    train_records = _to_gsm_records(train_frame)
    test_records = _to_gsm_records(test_frame)
    rng = random.Random(RANDOM_SEED)
    validation_indices = set(rng.sample(range(len(train_records)), VALIDATION_SIZE))
    train_pool = [row for index, row in enumerate(train_records) if index not in validation_indices]
    validation = [row for index, row in enumerate(train_records) if index in validation_indices]
    _write_jsonl(PROCESSED_DATA_DIR / "gsm8k_train_pool.jsonl", train_pool)
    _write_jsonl(PROCESSED_DATA_DIR / "gsm8k_validation.jsonl", validation)
    _write_jsonl(PROCESSED_DATA_DIR / "gsm8k_test.jsonl", test_records)
    _write_source_manifest(
        {
            "gsm8k": {
                "repo_id": GSM8K_REPO,
                "revision": GSM8K_REVISION,
                "license": DATASET_LICENSE,
                "train_rows": len(train_records),
                "validation_rows_held_out_from_train": len(validation),
                "validation_selection_seed": RANDOM_SEED,
                "validation_selection": "random sample without replacement from official train",
                "validation_indices_sha256": hashlib.sha256(
                    json.dumps(sorted(validation_indices)).encode("utf-8")
                ).hexdigest(),
                "train_pool_rows": len(train_pool),
                "official_test_rows": len(test_records),
                "train_sha256": sha256_file(train_path),
                "test_sha256": sha256_file(test_path),
                "train_filename": GSM8K_TRAIN_FILE,
                "test_filename": GSM8K_TEST_FILE,
            }
        }
    )
    return train_pool, validation, test_records


def _to_gsm_records(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Normalize a GSM8K split while preserving source order as stable IDs."""
    required = {"question", "answer"}
    if not required.issubset(frame.columns):
        raise ValueError(f"GSM8K parquet is missing columns: {sorted(required - set(frame.columns))}")
    return [
        {"case_id": str(index), "question": str(row.question), "answer": str(row.answer)}
        for index, row in enumerate(frame.itertuples(index=False))
    ]


def load_mmlu_sample() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Select a fixed subject-balanced test subset and separate dev demonstrations."""
    test_path = fetch_dataset_file(MMLU_REPO, MMLU_REVISION, MMLU_TEST_FILE)
    dev_path = fetch_dataset_file(MMLU_REPO, MMLU_REVISION, MMLU_DEV_FILE)
    test_frame = _read_parquet(test_path)
    dev_frame = _read_parquet(dev_path)
    required = {"question", "choices", "answer", "subject"}
    if not required.issubset(test_frame.columns) or not required.issubset(dev_frame.columns):
        raise ValueError("MMLU parquet does not contain the expected all-config fields")
    rng = random.Random(RANDOM_SEED)
    selected: list[dict[str, Any]] = []
    for subject in MMLU_SUBJECTS:
        rows = test_frame[test_frame["subject"] == subject].to_dict(orient="records")
        if len(rows) < MMLU_PER_SUBJECT:
            raise ValueError(f"MMLU subject {subject} has only {len(rows)} test rows")
        selected.extend(rng.sample(rows, MMLU_PER_SUBJECT))
    demos_by_subject: dict[str, list[dict[str, Any]]] = {}
    for subject in MMLU_SUBJECTS:
        demos_by_subject[subject] = dev_frame[dev_frame["subject"] == subject].to_dict(orient="records")
    sample = [
        {
            "case_id": f"{row['subject']}:{position}",
            "subject": str(row["subject"]),
            "question": str(row["question"]),
            "choices": [str(choice) for choice in row["choices"]],
            "answer": int(row["answer"]),
        }
        for position, row in enumerate(selected)
    ]
    if len(sample) != MMLU_SAMPLE_SIZE:
        raise ValueError(f"Expected {MMLU_SAMPLE_SIZE} MMLU rows, received {len(sample)}")
    _write_jsonl(PROCESSED_DATA_DIR / "mmlu_test_sample.jsonl", sample)
    _write_source_manifest(
        {
            "mmlu": {
                "repo_id": MMLU_REPO,
                "revision": MMLU_REVISION,
                "license": DATASET_LICENSE,
                "test_sample_rows": len(sample),
                "rows_per_subject": MMLU_PER_SUBJECT,
                "subjects": list(MMLU_SUBJECTS),
                "selection_seed": RANDOM_SEED,
                "test_sha256": sha256_file(test_path),
                "dev_sha256": sha256_file(dev_path),
                "test_filename": MMLU_TEST_FILE,
                "dev_filename": MMLU_DEV_FILE,
            }
        }
    )
    return sample, demos_by_subject


def save_training_jsonl(records: list[dict[str, str]], destination: Path) -> None:
    """Write chat-formatted supervised training records for MLX-LM."""
    examples = [
        {
            "messages": [
                {"role": "user", "content": gsm_training_prompt(row["question"])},
                {"role": "assistant", "content": row["answer"]},
            ]
        }
        for row in records
    ]
    _write_jsonl(destination, examples)


def gsm_training_prompt(question: str) -> str:
    """Return the same task framing used by the GSM8K prediction methods."""
    return (
        "Solve this grade-school math word problem. Show a concise sequence of "
        "calculations and end with the final numeric answer in the exact form "
        "#### number.\n\nQuestion: "
        f"{question}"
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSON Lines after creating the destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_source_manifest(updates: dict[str, Any]) -> None:
    """Merge downloaded source metadata into a tracked results manifest."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RESULTS_DIR / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update(updates)
    manifest["base_model"] = {
        "repo_id": BASE_MODEL_REPO,
        "revision": BASE_MODEL_REVISION,
        "license": MODEL_LICENSE,
        "quantization_bits": 4,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Download sources, verify official split sizes, and write deterministic split files."""
    train_pool, validation, test = split_gsm8k()
    mmlu, _ = load_mmlu_sample()
    print(
        json.dumps(
            {
                "gsm8k_train_pool": len(train_pool),
                "gsm8k_validation": len(validation),
                "gsm8k_official_test": len(test),
                "mmlu_test_sample": len(mmlu),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

