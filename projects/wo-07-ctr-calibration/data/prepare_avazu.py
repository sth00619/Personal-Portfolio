"""Validate the supplied Avazu archive and create a fixed temporal sample."""

from __future__ import annotations

import gzip
import hashlib
import os
import zlib
from collections import Counter
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
SOURCE = DATA_DIR / "avazu_train.gz"
SAMPLE = DATA_DIR / "avazu_sample.csv.gz"
EXPECTED_SHA256 = "2884596ea9351c8a9abc02bff1f7a4f0d161eac8caceadaaccfff31ec638b4ca"
EXPECTED_ROWS = 40_428_967
EXPECTED_DAYS = (
    "141021", "141022", "141023", "141024", "141025",
    "141026", "141027", "141028", "141029", "141030",
)
EXPECTED_COLUMNS = (
    "id", "click", "hour", "C1", "banner_pos", "site_id", "site_domain",
    "site_category", "app_id", "app_domain", "app_category", "device_id",
    "device_ip", "device_model", "device_type", "device_conn_type",
    "C14", "C15", "C16", "C17", "C18", "C19", "C20", "C21",
)
SAMPLE_MODULUS = 40
SAMPLE_OFFSET = 17
HASH_CHUNK_BYTES = 1024 * 1024


def source_sha256(path: Path) -> str:
    """Hash compressed bytes without loading the archive into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def sample_stream(
    source: Path, destination: Path, modulus: int = SAMPLE_MODULUS,
    offset: int = SAMPLE_OFFSET,
) -> dict[str, Any]:
    """Select rows by ID hash while auditing all logged hours and labels."""
    if modulus <= 0 or not 0 <= offset < modulus:
        raise ValueError("Invalid hash sample bucket")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    day_rows: Counter[str] = Counter()
    day_clicks: Counter[str] = Counter()
    sample_day_rows: Counter[str] = Counter()
    sample_day_clicks: Counter[str] = Counter()
    first_hour = previous_hour = ""
    row_count = 0
    try:
        with gzip.open(source, "rt", encoding="utf-8", newline="") as records, gzip.open(
            temporary, "wt", encoding="utf-8", newline="", compresslevel=3
        ) as sampled:
            header = records.readline()
            if tuple(header.rstrip("\r\n").split(",")) != EXPECTED_COLUMNS:
                raise ValueError("Unexpected Avazu competition schema")
            sampled.write(header)
            for row_count, line in enumerate(records, start=1):
                parts = line.split(",", 3)
                if len(parts) != 4 or parts[1] not in ("0", "1"):
                    raise ValueError(f"Invalid Avazu record at row {row_count}")
                hour = parts[2]
                if len(hour) != 8 or not hour.isdigit() or hour < previous_hour:
                    raise ValueError(f"Invalid or unsorted hour at row {row_count}")
                if not first_hour:
                    first_hour = hour
                previous_hour = hour
                day = hour[:6]
                click = int(parts[1])
                day_rows[day] += 1
                day_clicks[day] += click
                if zlib.crc32(parts[0].encode("ascii")) % modulus == offset:
                    sampled.write(line)
                    sample_day_rows[day] += 1
                    sample_day_clicks[day] += click
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "source_rows": row_count,
        "source_day_rows": dict(sorted(day_rows.items())),
        "source_day_clicks": dict(sorted(day_clicks.items())),
        "sample_rows": sum(sample_day_rows.values()),
        "sample_day_rows": dict(sorted(sample_day_rows.items())),
        "sample_day_clicks": dict(sorted(sample_day_clicks.items())),
        "first_hour": first_hour,
        "last_hour": previous_hour,
        "sample_modulus": modulus,
        "sample_offset": offset,
        "sample_key": "crc32(id)",
    }


def prepare_avazu(source: Path = SOURCE, sample: Path = SAMPLE) -> dict[str, Any]:
    """Verify the specific supplied archive and enforce the declared sample."""
    if not source.is_file():
        raise FileNotFoundError(f"Copy the Kaggle train.gz archive to {source}")
    digest = source_sha256(source)
    if digest != EXPECTED_SHA256:
        raise ValueError("Avazu source SHA-256 differs from the audited archive")
    audit = sample_stream(source, sample)
    if audit["source_rows"] != EXPECTED_ROWS or tuple(audit["source_day_rows"]) != EXPECTED_DAYS:
        sample.unlink(missing_ok=True)
        raise ValueError("Avazu source row count or days differ from the audited archive")
    return {
        "source": "Kaggle Avazu CTR Prediction train.gz",
        "source_size_bytes": source.stat().st_size,
        "source_sha256": digest,
        **audit,
    }
