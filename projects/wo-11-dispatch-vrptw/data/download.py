"""공식 Solomon 인스턴스와 NYC TLC 수요 자료를 내려받는다."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
SOLOMON_URL = "https://www.sintef.no/globalassets/project/top/vrptw/solomon/solomon-100.zip"
TLC_TRIPS_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
TAXI_ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip"
USER_AGENT = "WO-11 reproducible research download"
BLOCK_BYTES = 1 << 20

ASSETS = {
    "solomon-100.zip": SOLOMON_URL,
    "yellow_tripdata.parquet": TLC_TRIPS_URL,
    "taxi_zones.zip": TAXI_ZONES_URL,
}


def sha256_file(path: Path) -> str:
    """파일의 SHA-256 체크섬을 계산한다."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """완성된 파일은 재사용하고 새 파일은 임시 경로를 거쳐 저장한다."""
    if destination.is_file() and destination.stat().st_size > 0:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=BLOCK_BYTES)
        if temporary.stat().st_size == 0:
            raise ValueError(f"빈 파일을 받았습니다: {url}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def extract_zip(source: Path, destination: Path) -> None:
    """ZIP 내용을 별도 원본 디렉터리에 안전하게 푼다."""
    marker = destination / ".complete"
    if marker.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as archive:
        root = destination.resolve()
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError(f"안전하지 않은 ZIP 경로: {member.filename}")
        archive.extractall(destination)
    marker.touch()


def main() -> None:
    """세 원본을 다운로드·압축 해제하고 검증용 체크섬을 출력한다."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in ASSETS.items():
        destination = RAW_DIR / filename
        download(url, destination)
        print(f"{filename}: bytes={destination.stat().st_size} sha256={sha256_file(destination)}")
    extract_zip(RAW_DIR / "solomon-100.zip", RAW_DIR / "solomon")
    extract_zip(RAW_DIR / "taxi_zones.zip", RAW_DIR / "taxi_zones")


if __name__ == "__main__":
    main()
