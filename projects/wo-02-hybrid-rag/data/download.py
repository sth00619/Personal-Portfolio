"""Download and verify the official BEIR SciFact archive."""

import hashlib
import os
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

DEFAULT_URL = (
    "https://public.ukp.informatik.tu-darmstadt.de/"
    "thakur/BEIR/datasets/scifact.zip"
)
URL_ENVIRONMENT_VARIABLE = "BEIR_SCIFACT_URL"
EXPECTED_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
DATA_DIRECTORY = Path(__file__).resolve().parent


def ensure_dataset() -> Path:
    """Download, checksum, and safely extract SciFact when it is absent."""
    target = DATA_DIRECTORY / "scifact"
    required = (target / "corpus.jsonl", target / "qrels" / "test.tsv")
    if all(path.exists() for path in required):
        return target

    archive = DATA_DIRECTORY / "scifact.zip"
    if not archive.exists():
        url = os.environ.get(URL_ENVIRONMENT_VARIABLE, DEFAULT_URL)
        urlretrieve(url, archive)
    digest = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    if digest != EXPECTED_MD5:
        raise ValueError(f"SciFact checksum mismatch: {digest} != {EXPECTED_MD5}")

    with ZipFile(archive) as zipped:
        root = DATA_DIRECTORY.resolve()
        for member in zipped.infolist():
            destination = (DATA_DIRECTORY / member.filename).resolve()
            if destination != root and root not in destination.parents:
                raise ValueError(f"Unsafe archive member: {member.filename}")
        zipped.extractall(DATA_DIRECTORY)

    if not all(path.exists() for path in required):
        raise FileNotFoundError("SciFact archive is missing a required test file")
    return target


def main() -> None:
    """Print the verified local dataset path."""
    print(ensure_dataset())


if __name__ == "__main__":
    main()
