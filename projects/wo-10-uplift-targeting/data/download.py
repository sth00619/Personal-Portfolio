"""Criteo 공식 수정본 Uplift RCT 로그를 내려받고 크기를 확인한다."""

from __future__ import annotations

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

DATA_URL = "https://criteostorage.blob.core.windows.net/criteo-research-datasets/criteo-uplift-v2.1.csv.gz"
EXPECTED_BYTES = 311_422_618
EXPECTED_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
CHUNK_BYTES = 1 << 20
RANGE_BYTES = 8 << 20
DOWNLOAD_WORKERS = 8
DEFAULT_DESTINATION = Path(__file__).resolve().parent / "criteo-uplift-v2.1.csv.gz"


def sha256_file(path: Path) -> str:
    """원본 압축 파일의 SHA-256을 계산한다."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(destination: Path) -> tuple[int, str]:
    """원본을 범위별 병렬 전송하고 부분 파일은 이어 받는다."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    current_size = destination.stat().st_size if destination.exists() else 0
    if current_size > EXPECTED_BYTES:
        raise ValueError(f"예상 크기보다 큰 원본: {current_size} bytes")

    def fetch(start: int, end: int) -> Path:
        """지정한 바이트 범위를 별도 파일에 내려받아 헤더를 검증한다."""
        part = destination.with_name(f"{destination.name}.{start}.part")
        request = Request(DATA_URL, headers={"Range": f"bytes={start}-{end}"})
        with urlopen(request, timeout=120) as response, part.open("wb") as output:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{EXPECTED_BYTES}":
                raise ValueError(f"Range 응답이 예상과 다릅니다: {start}-{end}")
            for block in iter(lambda: response.read(CHUNK_BYTES), b""):
                output.write(block)
        if part.stat().st_size != end - start + 1:
            raise ValueError(f"부분 파일의 길이가 다릅니다: {part}")
        return part

    ranges = [(start, min(start + RANGE_BYTES - 1, EXPECTED_BYTES - 1)) for start in range(current_size, EXPECTED_BYTES, RANGE_BYTES)]
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        parts = list(pool.map(lambda bounds: fetch(*bounds), ranges))
    with destination.open("ab") as output:
        for part in parts:
            with part.open("rb") as source:
                for block in iter(lambda: source.read(CHUNK_BYTES), b""):
                    output.write(block)
            part.unlink()
    size = destination.stat().st_size
    if size != EXPECTED_BYTES:
        raise ValueError(f"다운로드 크기가 공식 배포 파일과 다릅니다: {size} bytes")
    digest = sha256_file(destination)
    if digest != EXPECTED_SHA256:
        raise ValueError(f"원본 SHA-256이 다릅니다: {digest}")
    return size, digest


def main() -> None:
    """명령행 경로에 원본을 다운로드하고 크기·체크섬을 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    size, digest = download(args.output)
    print(f"bytes={size} sha256={digest} path={args.output}")


if __name__ == "__main__":
    main()
