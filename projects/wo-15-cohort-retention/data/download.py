"""Download the nine Olist source CSVs from a revision-pinned public mirror."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


MIRROR_REVISION = "5acf1f37d7197d4979e714721a1ec13a7c3da728"
MIRROR_ROOT = "https://huggingface.co/datasets/bulutttt/olist-raw-data/resolve"
RAW_DIR = Path(__file__).resolve().parent / "raw"
BUFFER_SIZE = 1024 * 1024
MAX_DOWNLOADS = 4


@dataclass(frozen=True)
class SourceFile:
    """Expected bytes for one dataset file at a fixed mirror revision."""

    size: int
    sha256: str = ""


FILES = {
    "olist_orders_dataset.csv": SourceFile(
        17_654_914, "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"
    ),
    "olist_customers_dataset.csv": SourceFile(
        9_033_957, "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2"
    ),
    "olist_order_items_dataset.csv": SourceFile(
        15_438_671, "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279"
    ),
    "olist_order_payments_dataset.csv": SourceFile(
        5_777_138, "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0"
    ),
    "olist_order_reviews_dataset.csv": SourceFile(
        14_451_670, "012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7"
    ),
    "olist_products_dataset.csv": SourceFile(
        2_379_446, "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc"
    ),
    "olist_sellers_dataset.csv": SourceFile(
        174_703, "1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e"
    ),
    "olist_geolocation_dataset.csv": SourceFile(
        61_273_883, "b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6"
    ),
    "product_category_name_translation.csv": SourceFile(
        2_613, "a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278"
    ),
}


def digest(path: Path) -> str:
    """Calculate SHA-256 incrementally to keep memory use bounded."""

    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BUFFER_SIZE), b""):
            hasher.update(block)
    return hasher.hexdigest()


def download_one(filename: str, source: SourceFile, force: bool = False) -> str:
    """Download and byte-validate one CSV using an atomic temporary file."""

    destination = RAW_DIR / filename
    if destination.exists() and not force:
        if destination.stat().st_size != source.size:
            raise ValueError(f"Unexpected file size for {filename}")
        file_digest = digest(destination)
        if source.sha256 and file_digest != source.sha256:
            raise ValueError(f"SHA-256 mismatch for existing {filename}: {file_digest}")
        return f"verified existing {filename} sha256={file_digest}"

    temporary = destination.with_suffix(destination.suffix + ".part")
    url = f"{MIRROR_ROOT}/{MIRROR_REVISION}/{filename}"
    try:
        with urllib.request.urlopen(url) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=BUFFER_SIZE)
        if temporary.stat().st_size != source.size:
            raise ValueError(f"Unexpected file size for {filename}")
        file_digest = digest(temporary)
        if source.sha256 and file_digest != source.sha256:
            raise ValueError(f"SHA-256 mismatch for {filename}: {file_digest}")
        temporary.replace(destination)
        return f"downloaded {filename} bytes={source.size} sha256={file_digest}"
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    """Download the complete source bundle without storing credentials."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOADS) as executor:
        futures = [
            executor.submit(download_one, name, source, args.force)
            for name, source in FILES.items()
        ]
        for future in futures:
            print(future.result(), flush=True)


if __name__ == "__main__":
    main()

