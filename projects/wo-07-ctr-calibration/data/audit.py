"""Inspect downloaded Criteo shards without exposing individual records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


DATA_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = DATA_DIR.parent / "results" / "data_audit.json"
SAMPLE_ROWS_PER_DAY = 40_000
DATE_FILES = (
    "2015-02-15.parquet",
    "2015-02-16.parquet",
    "2015-02-17.parquet",
    "2015-02-18.parquet",
)


def sha256(path: Path) -> str:
    """Return a file digest without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_file(path: Path) -> dict[str, object]:
    """Summarize schema and a fixed prefix from one dated shard."""
    parquet = pq.ParquetFile(path)
    frames: list[pd.DataFrame] = []
    remaining = SAMPLE_ROWS_PER_DAY
    for batch in parquet.iter_batches(batch_size=min(remaining, 10_000)):
        frame = batch.to_pandas()
        frames.append(frame.iloc[:remaining])
        remaining -= min(len(frame), remaining)
        if remaining == 0:
            break
    if not frames:
        raise ValueError(f"Empty shard: {path}")
    sample = pd.concat(frames, ignore_index=True)
    label_name = "label" if "label" in sample.columns else "click"
    if label_name not in sample:
        raise ValueError(f"No click label in {path}")
    label = pd.to_numeric(sample[label_name], errors="raise")
    if not label.isin([0, 1]).all():
        raise ValueError(f"Nonbinary click label in {path}")
    numeric_columns = [name for name in sample if name.startswith("integer_feature_")]
    categorical_columns = [name for name in sample if name.startswith("categorical_feature_")]
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "parquet_rows": parquet.metadata.num_rows,
        "sample_rows": len(sample),
        "sample_positive": int(label.sum()),
        "sample_positive_rate": float(label.mean()),
        "column_names": sample.columns.tolist(),
        "dtypes": {name: str(dtype) for name, dtype in sample.dtypes.items()},
        "numeric_feature_count": len(numeric_columns),
        "categorical_feature_count": len(categorical_columns),
        "missing_count": {name: int(sample[name].isna().sum()) for name in sample},
        "categorical_cardinality": {
            name: int(sample[name].nunique(dropna=True)) for name in categorical_columns
        },
    }


def main() -> None:
    """Write machine readable observations for the four fixed source shards."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit = {"source": "criteo/CriteoClickLogs", "files": []}
    for filename in DATE_FILES:
        audit["files"].append(audit_file(DATA_DIR / filename))
    OUTPUT_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
