"""Download and verify the official FUNSD archive without committing source data."""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
ARCHIVE_PATH = DATA_DIR / "funsd.zip"
RAW_DIR = DATA_DIR / "raw"
DATASET_DIR = RAW_DIR / "dataset"
DATASET_URL = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
EXPECTED_SHA256 = "c31735649e4f441bcbb4fd0f379574f7520b42286e80b01d80b445649d54761f"
EXPECTED_DOCUMENT_COUNTS = {"training_data": 149, "testing_data": 50}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file, reading it in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset() -> Path:
    """Fetch the official archive, verify it, and extract only dataset files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE_PATH.exists():
        request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "WO-21-data-loader/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, ARCHIVE_PATH.open("wb") as target:
            shutil.copyfileobj(response, target)
    observed = sha256_file(ARCHIVE_PATH)
    if observed != EXPECTED_SHA256:
        ARCHIVE_PATH.unlink(missing_ok=True)
        raise ValueError(f"FUNSD archive SHA-256 mismatch: expected {EXPECTED_SHA256}, got {observed}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        for member in archive.infolist():
            path = Path(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe archive member: {member.filename}")
            if member.filename.startswith("dataset/"):
                archive.extract(member, RAW_DIR)
    for split, expected_count in EXPECTED_DOCUMENT_COUNTS.items():
        observed_count = len(list((DATASET_DIR / split / "annotations").glob("*.json")))
        if observed_count != expected_count:
            raise ValueError(f"FUNSD {split} document count mismatch: expected {expected_count}, got {observed_count}")
    return DATASET_DIR


if __name__ == "__main__":
    print(f"FUNSD data ready: {download_dataset()}")
