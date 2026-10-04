"""Retrieve verified OBD campaign members from the official ZIP archive."""

from __future__ import annotations

import shutil
import zlib
from dataclasses import dataclass
from pathlib import Path

from remotezip import RemoteZip


ARCHIVE_URL = "https://research.zozo.com/data_release/open_bandit_dataset.zip"
RAW = Path(__file__).resolve().parent / "raw"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class Member:
    """Expected ZIP metadata of one original dataset file."""

    archive_name: str
    relative_path: str
    size: int
    crc: int


MEMBERS = (
    Member("open_bandit_dataset/random/men/men.csv", "random/men/men.csv", 151946449, 2126893868),
    Member("open_bandit_dataset/random/men/item_context.csv", "random/men/item_context.csv", 4287, 3881471782),
    Member("open_bandit_dataset/bts/men/men.csv", "bts/men/men.csv", 1332891122, 90067629),
)


def verify_local(member: Member) -> bool:
    """Compare a local extracted member with expected size and ZIP CRC."""
    target = RAW / member.relative_path
    if not target.exists() or target.stat().st_size != member.size:
        return False
    crc = 0
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            crc = zlib.crc32(block, crc)
    return crc == member.crc


def copy_member(archive: RemoteZip, member: Member) -> None:
    """Stream one ZIP member and verify its size and CRC before publishing."""
    info = archive.getinfo(member.archive_name)
    if info.file_size != member.size or info.CRC != member.crc:
        raise ValueError(f"Unexpected archive member metadata: {member.archive_name}")
    target = RAW / member.relative_path
    if verify_local(member):
        print(f"Present: {member.relative_path}", flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with archive.open(info) as source, temporary.open("wb") as output:
        shutil.copyfileobj(source, output, CHUNK_SIZE)
    if temporary.stat().st_size != member.size:
        raise ValueError(f"Incomplete archive member: {member.archive_name}")
    temporary.replace(target)
    print(f"Verified: {member.relative_path}", flush=True)


def main() -> None:
    """Download only full Men campaign logs needed for reproducible evaluation."""
    RAW.mkdir(parents=True, exist_ok=True)
    with RemoteZip(ARCHIVE_URL) as archive:
        for member in MEMBERS:
            copy_member(archive, member)


if __name__ == "__main__":
    main()
