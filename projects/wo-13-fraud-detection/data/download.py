"""Download and verify the IEEE-CIS training files needed by WO-13."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


RAW_DIR = Path(__file__).resolve().parent / "raw"
CHUNK_BYTES = 4 * 1024 * 1024
USER_AGENT = "wo-13-fraud-detection/1.0"


@dataclass(frozen=True)
class RemoteFile:
    """Describe a mirrored competition file and its integrity constraints."""

    name: str
    url: str
    expected_bytes: int
    sha256: str


FILES = (
    RemoteFile(
        name="train_transaction.csv",
        url=(
            "https://huggingface.co/datasets/aliceczr/ieee-fraud-detection/"
            "resolve/main/train_transaction.csv"
        ),
        expected_bytes=683_351_067,
        sha256="3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642",
    ),
    RemoteFile(
        name="train_identity.csv",
        url=(
            "https://huggingface.co/datasets/aliceczr/ieee-fraud-detection/"
            "resolve/main/train_identity.csv"
        ),
        expected_bytes=26_529_680,
        sha256="b63c725d8377be90a995268d97f347c17d456b95db45807adcf9f59cd603c37c",
    ),
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one local file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(spec: RemoteFile, destination: Path) -> None:
    """Stream a remote file and atomically replace a partial download."""

    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response, partial.open("wb") as output:
        while chunk := response.read(CHUNK_BYTES):
            output.write(chunk)
    partial.replace(destination)


def validate_file(spec: RemoteFile, path: Path) -> dict[str, object]:
    """Validate a downloaded file against pinned size and hash metadata."""

    actual_bytes = path.stat().st_size
    actual_sha256 = sha256_file(path)
    if actual_bytes != spec.expected_bytes:
        raise ValueError(
            f"{spec.name}: expected {spec.expected_bytes} bytes, got {actual_bytes}"
        )
    if actual_sha256 != spec.sha256:
        raise ValueError(
            f"{spec.name}: expected SHA-256 {spec.sha256}, got {actual_sha256}"
        )
    return {
        **asdict(spec),
        "path": str(path.relative_to(RAW_DIR.parent.parent)),
        "actual_bytes": actual_bytes,
        "actual_sha256": actual_sha256,
    }


def main() -> None:
    """Download missing inputs and write a local integrity manifest."""

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for spec in FILES:
        destination = RAW_DIR / spec.name
        if not destination.exists():
            print(f"downloading {spec.name}", flush=True)
            download_file(spec, destination)
        record = validate_file(spec, destination)
        records.append(record)
        print(
            f"validated {spec.name}: {record['actual_bytes']} bytes, "
            f"sha256={record['actual_sha256']}",
            flush=True,
        )
    (RAW_DIR / "manifest.json").write_text(
        json.dumps({"files": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

