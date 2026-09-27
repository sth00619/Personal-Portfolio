"""Download and verify the pinned Quora duplicate-pairs parquet file."""

import hashlib
import os
from pathlib import Path
from urllib.request import urlretrieve

DATASET_REVISION = "41f699770310302022a4dd75d4cf903bfef9ea46"
DEFAULT_URL = (
    "https://huggingface.co/datasets/sentence-transformers/quora-duplicates/"
    f"resolve/{DATASET_REVISION}/pair-class/train-00000-of-00001.parquet?download=true"
)
URL_ENVIRONMENT_VARIABLE = "QUORA_PAIRS_URL"
EXPECTED_SHA256 = "71954cb44e706ad26675731b6138995763c6dc8079c14f1fdf956122ccea587f"
DATA_DIRECTORY = Path(__file__).resolve().parent
DATASET_PATH = DATA_DIRECTORY / "quora-pairs.parquet"


def ensure_dataset() -> Path:
    """Download the pinned dataset file and validate its SHA-256 digest."""
    if not DATASET_PATH.exists():
        urlretrieve(os.environ.get(URL_ENVIRONMENT_VARIABLE, DEFAULT_URL), DATASET_PATH)
    digest = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Quora dataset checksum mismatch: {digest}")
    return DATASET_PATH


def main() -> None:
    """Print the verified local dataset path."""
    print(ensure_dataset())


if __name__ == "__main__":
    main()
