"""Download the pinned public BIRD Mini-Dev SQLite data outside Git tracking."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATASET_REVISION = "f65faf4ae3b638c1fa6df1d3370c8d92c8366301"
DATASET_URL = (
    "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/"
    f"{DATASET_REVISION}/data/mini_dev_sqlite-00000-of-00001.json"
)
DATABASE_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
DATASET_SHA256 = "88ceb0710163cae46a256ecea8f0a8c98286599530b60587fda5c3cfe57d45d2"
DATABASE_SHA256 = "cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f"


def download(url: str, destination: Path) -> None:
    """Fetch a public asset with a clear progress-free command line workflow."""
    if destination.exists() and destination.stat().st_size > 0:
        print(f"Using existing {destination.name} ({destination.stat().st_size} bytes)")
        return
    request = urllib.request.Request(url, headers={"User-Agent": "WO-16 portfolio project"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    print(f"Downloaded {destination.name} ({destination.stat().st_size} bytes)")


def sha256(path: Path) -> str:
    """Calculate a stable content digest for provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    """Download and unpack the benchmark files required for the experiment."""
    DATA.mkdir(parents=True, exist_ok=True)
    dataset_path = DATA / "mini_dev_sqlite.json"
    archive_path = DATA / "minidev.zip"
    download(DATASET_URL, dataset_path)
    download(DATABASE_URL, archive_path)
    if sha256(dataset_path) != DATASET_SHA256:
        raise ValueError("Dataset SHA-256 mismatch; do not score an unpinned revision")
    if sha256(archive_path) != DATABASE_SHA256:
        raise ValueError("Database archive SHA-256 mismatch; inspect the source before use")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(DATA)
    manifest = {
        "dataset": "BIRD Mini-Dev SQLite, official 500-question subset",
        "dataset_repository": "https://huggingface.co/datasets/birdsql/bird_mini_dev",
        "dataset_repository_revision": DATASET_REVISION,
        "dataset_file_sha256": sha256(dataset_path),
        "dataset_license": "CC BY-SA 4.0; follow BIRD source terms and cite the benchmark",
        "database_archive_source": DATABASE_URL,
        "database_archive_sha256": sha256(archive_path),
        "model": "mlx-community/Qwen2.5-Coder-3B-Instruct-4bit",
        "model_license": "qwen-research",
        "model_revision": "3dd939c621c08e5753d5b89f35a2642cd83b98ca",
    }
    (ROOT / "docs" / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {ROOT / 'docs' / 'source_manifest.json'}")


if __name__ == "__main__":
    main()
