"""Download the official BEIR SciFact archive; raw data stays outside git."""

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
MD5 = "5f7d1de60b170fc8027bb7898e2efca1"  # Published in BEIR's dataset table.
HERE = Path(__file__).resolve().parent


def ensure_dataset() -> Path:
    """Download, verify, and safely extract the official SciFact archive once."""
    target = HERE / "scifact"
    if (target / "corpus.jsonl").exists() and (target / "qrels" / "test.tsv").exists():
        return target
    archive = HERE / "scifact.zip"
    if not archive.exists():
        urlretrieve(os.environ.get(URL_ENVIRONMENT_VARIABLE, DEFAULT_URL), archive)
    digest = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    if digest != MD5:
        raise ValueError("SciFact download checksum differs from BEIR's published MD5")
    with ZipFile(archive) as zipped:
        for member in zipped.infolist():
            destination = (HERE / member.filename).resolve()
            if HERE.resolve() not in destination.parents and destination != HERE.resolve():
                raise ValueError(f"Unsafe archive member: {member.filename}")
        zipped.extractall(HERE)
    if not (target / "corpus.jsonl").exists():
        raise FileNotFoundError("SciFact archive did not contain corpus.jsonl")
    return target


def main() -> None:
    """Print the verified local dataset directory."""
    print(ensure_dataset())


if __name__ == "__main__":
    main()
