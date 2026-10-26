"""Download verified Home Credit files from a revision-pinned public transport mirror."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path


MIRROR_REVISION = "84ffcf43ebdc369933b3d95ea950c8221d3117d5"
MIRROR_ROOT = "https://huggingface.co/datasets/jamirc/home_credit_default_risk/resolve"
RAW_DIR = Path(__file__).resolve().parent / "raw"
BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True)
class SourceFile:
    """Describe one locally named, size- and hash-verified source file."""

    remote_name: str
    size: int
    sha256: str


FILES = {
    "application_train.csv": SourceFile(
        remote_name="application_tr.csv",
        size=165_448_797,
        sha256="3a230e819e297d7045bbfefdb2d9afa4afef1ab3a8a4bd039c1d3497cb67cb50",
    ),
    "bureau.csv": SourceFile(
        remote_name="bureau.csv",
        size=171_733_123,
        sha256="75ff59e803bd1c4a02530d13cbf3309107c34ee88cb7d63ec62b2685cac764cb",
    ),
    "previous_application.csv": SourceFile(
        remote_name="previous_application.csv",
        size=406_367_240,
        sha256="53bbcd69f3fe0f43a87b6426f88139346c061955e9c90e29ba6ae2f59637c053",
    ),
}


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(path: Path, source: SourceFile) -> None:
    """Validate both byte size and checksum against the evidence contract."""

    if path.stat().st_size != source.size:
        raise ValueError(f"{path.name}: unexpected byte size")
    actual = sha256(path)
    if actual != source.sha256:
        raise ValueError(f"{path.name}: SHA-256 mismatch ({actual})")


def download(destination: Path, source: SourceFile, force: bool = False) -> None:
    """Download one file atomically and validate before exposing the final name."""

    if destination.exists() and not force:
        validate(destination, source)
        print(f"verified existing {destination.name}")
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    url = f"{MIRROR_ROOT}/{MIRROR_REVISION}/{source.remote_name}"
    try:
        with urllib.request.urlopen(url) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=BUFFER_SIZE)
        validate(temporary, source)
        temporary.replace(destination)
        print(f"downloaded and verified {destination.name}")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    """Download every required raw table to the ignored local raw directory."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for local_name, source in FILES.items():
        download(RAW_DIR / local_name, source, force=args.force)


if __name__ == "__main__":
    main()

