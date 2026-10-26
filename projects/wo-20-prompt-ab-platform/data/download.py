"""Download and verify the official SQuAD 2.0 development JSON file."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
DESTINATION = DATA_DIR / "squad_v2_dev.json"
TEMPORARY = DATA_DIR / "squad_v2_dev.json.tmp"
SOURCE_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json"
EXPECTED_SHA256 = "80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8"
EXPECTED_BYTES = 4_370_528
CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset() -> dict[str, str | int]:
    """Download the pinned official dev file and reject unexpected bytes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "WO-20-prompt-ab-platform/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, TEMPORARY.open("wb") as output:
            while chunk := response.read(CHUNK_BYTES):
                output.write(chunk)
        size = TEMPORARY.stat().st_size
        digest = sha256_file(TEMPORARY)
        if size != EXPECTED_BYTES or digest != EXPECTED_SHA256:
            raise ValueError(
                f"SQuAD dev integrity check failed: bytes={size}, sha256={digest}"
            )
        os.replace(TEMPORARY, DESTINATION)
        return {"path": str(DESTINATION), "bytes": size, "sha256": digest}
    finally:
        TEMPORARY.unlink(missing_ok=True)


if __name__ == "__main__":
    print(download_dataset())
