"""Download and verify the M5 files needed by WO-12."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


RAW_DIR = Path(__file__).resolve().parent / "raw"
CHUNK_BYTES = 1024 * 1024
USER_AGENT = "wo-12-demand-quantile-forecast/1.0"


@dataclass(frozen=True)
class RemoteFile:
    """Describe a remotely hosted source file and its integrity constraints."""

    name: str
    url: str
    expected_bytes: int
    sha256: str


FILES = (
    RemoteFile(
        name="sales_train_evaluation.csv",
        url=(
            "https://huggingface.co/datasets/sktime/tsf-datasets/resolve/main/"
            "m5-forecasting-accuracy/sales_train_evaluation.csv"
        ),
        expected_bytes=121_736_518,
        sha256="4b4a47c44c38380d2a9168216fea8c9ff2f31b1ddb772f8a0995952a038b8aa0",
    ),
    RemoteFile(
        name="calendar.csv",
        url=(
            "https://huggingface.co/datasets/sktime/tsf-datasets/resolve/main/"
            "m5-forecasting-accuracy/calendar.csv"
        ),
        expected_bytes=103_469,
        sha256="d12b5914ef03e66649adf5dd9e996e6602251c22b7a6af8f1f7e3aa12f8860f5",
    ),
)


def sha256_file(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(spec: RemoteFile, destination: Path) -> None:
    """Stream a source file to disk and replace a partial file atomically."""

    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response, partial.open("wb") as output:
        while chunk := response.read(CHUNK_BYTES):
            output.write(chunk)
    partial.replace(destination)


def validate_file(spec: RemoteFile, path: Path) -> dict[str, object]:
    """Validate byte size and, when pinned, the source SHA-256 digest."""

    actual_bytes = path.stat().st_size
    actual_sha256 = sha256_file(path)
    if actual_bytes != spec.expected_bytes:
        raise ValueError(
            f"{spec.name}: expected {spec.expected_bytes} bytes, got {actual_bytes}"
        )
    if spec.sha256 and actual_sha256 != spec.sha256:
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
    """Download missing data, validate every file, and write a local manifest."""

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for spec in FILES:
        destination = RAW_DIR / spec.name
        if not destination.exists():
            print(f"downloading {spec.name}", flush=True)
            download_file(spec, destination)
        record = validate_file(spec, destination)
        manifest.append(record)
        print(
            f"validated {spec.name}: {record['actual_bytes']} bytes, "
            f"sha256={record['actual_sha256']}",
            flush=True,
        )
    manifest_path = RAW_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps({"files": manifest}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

