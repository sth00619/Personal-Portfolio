"""Fetch fixed iPinYou archive byte ranges without redistributing source data."""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ARCHIVE_URL = "https://ndownloader.figshare.com/files/10082688"
DATA_DIR = Path(__file__).resolve().parent / "raw"
CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class FileSpec:
    """Describe a byte range and verified checksum within the fixed archive."""

    name: str
    start: int
    end: int
    algorithm: str
    digest: str


FILES = (
    FileSpec("imp.20130606.prefix.bz2", 2816132621, 2832919836, "sha256", "bf0ca4cd9f5360c08e9574c69cf27e312c9fec848b7a914072451bb97d89238d"),
    FileSpec("imp.20130607.prefix.bz2", 2937693445, 2954480660, "sha256", "2a48c5c4764654f36a6a838afe5655286e324acae16efc232171560c5a716882"),
    FileSpec("imp.20130608.prefix.bz2", 3057239361, 3074026576, "sha256", "90bc84d11ad909c1f312381ca56adcded0c17bc8a8a6e76a687653e3b336c33c"),
    FileSpec("imp.20130609.txt.bz2", 3166914475, 3275021758, "md5", "378754f00fa69784b19c5db6305783cc"),
    FileSpec("clk.20130606.txt.bz2", 2815347876, 2815447191, "md5", "cdc968d27326dbe0e7dbd72a00affd53"),
    FileSpec("clk.20130607.txt.bz2", 2815447286, 2815537354, "md5", "77b8df54b9a230e2875ca4ab01cf0e02"),
    FileSpec("clk.20130608.txt.bz2", 2815537449, 2815637222, "md5", "faa44dbd0c35e0735e5575446da43e23"),
    FileSpec("clk.20130609.txt.bz2", 2815637317, 2815733134, "md5", "9668caa2520bec15e7d5f82e61cf6288"),
)


def digest_file(path: Path, algorithm: str) -> str:
    """Hash a local compressed file in bounded memory."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(spec: FileSpec) -> None:
    """Download and verify one exact member range of the immutable archive."""
    target = DATA_DIR / spec.name
    if target.exists() and digest_file(target, spec.algorithm) == spec.digest:
        print(f"Verified {spec.name}")
        return
    request = urllib.request.Request(
        ARCHIVE_URL, headers={"Range": f"bytes={spec.start}-{spec.end}"}
    )
    temporary = target.with_suffix(target.suffix + ".tmp")
    with urllib.request.urlopen(request, timeout=120) as response:
        expected_range = f"bytes {spec.start}-{spec.end}/"
        if response.status != 206 or not response.headers.get("Content-Range", "").startswith(expected_range):
            raise ValueError(f"Server did not honor byte range for {spec.name}")
        with temporary.open("wb") as handle:
            while block := response.read(CHUNK_BYTES):
                handle.write(block)
    if temporary.stat().st_size != spec.end - spec.start + 1:
        raise ValueError(f"Incomplete download: {spec.name}")
    if digest_file(temporary, spec.algorithm) != spec.digest:
        raise ValueError(f"Checksum mismatch: {spec.name}")
    temporary.replace(target)
    print(f"Downloaded {spec.name}")


def main() -> None:
    """Fetch only three training prefixes, one full replay day, and click logs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for spec in FILES:
        fetch(spec)


if __name__ == "__main__":
    main()
