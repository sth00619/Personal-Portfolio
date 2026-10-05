"""NYC TLC 기록에서 합성 배달 주문에 사용할 수요 프로파일을 추출한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapefile

FEET_PER_MILE = 5_280.0
MIN_TRIP_MINUTES = 2.0
MAX_TRIP_MINUTES = 90.0
MIN_TRIP_MILES = 0.1
MAX_TRIP_MILES = 30.0
TARGET_SAMPLE_ROWS = 50_000
BATCH_ROWS = 200_000
SAMPLE_SEED = 42
PARQUET_COLUMNS = (
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_distance",
)


@dataclass(frozen=True)
class DemandProfile:
    """시간대 수요와 실제 OD·이동시간 표본."""

    hour_counts: np.ndarray
    pickup: np.ndarray
    dropoff: np.ndarray
    direct_minutes: np.ndarray
    pickup_hours: np.ndarray
    valid_rows: int
    source_rows: int
    minutes_per_mile: float


def zone_centers(shapefile_path: Path) -> dict[int, tuple[float, float]]:
    """공식 Taxi Zone 폴리곤의 경계상자 중심을 마일 좌표로 변환한다."""
    reader = shapefile.Reader(str(shapefile_path))
    field_names = [field[0] for field in reader.fields[1:]]
    location_field = next(name for name in field_names if name.lower() == "locationid")
    centers: dict[int, tuple[float, float]] = {}
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        minimum_x, minimum_y, maximum_x, maximum_y = shape_record.shape.bbox
        centers[int(record[location_field])] = (
            (minimum_x + maximum_x) / (2.0 * FEET_PER_MILE),
            (minimum_y + maximum_y) / (2.0 * FEET_PER_MILE),
        )
    if not centers:
        raise ValueError("Taxi Zone 좌표를 읽지 못했습니다")
    origin_x = min(value[0] for value in centers.values())
    origin_y = min(value[1] for value in centers.values())
    return {zone: (x - origin_x, y - origin_y) for zone, (x, y) in centers.items()}


def extract_profile(parquet_path: Path, shapefile_path: Path) -> DemandProfile:
    """전체 Parquet을 감사하며 유효 행 집계와 확률 표본을 만든다."""
    centers = zone_centers(shapefile_path)
    parquet = pq.ParquetFile(parquet_path)
    source_rows = parquet.metadata.num_rows
    random = np.random.default_rng(SAMPLE_SEED)
    sample_probability = min(1.0, TARGET_SAMPLE_ROWS / max(source_rows, 1))
    hour_counts = np.zeros(24, dtype=np.int64)
    sample_frames: list[pd.DataFrame] = []
    valid_rows = 0

    for batch in parquet.iter_batches(batch_size=BATCH_ROWS, columns=list(PARQUET_COLUMNS)):
        frame = batch.to_pandas()
        duration = (frame["tpep_dropoff_datetime"] - frame["tpep_pickup_datetime"]).dt.total_seconds() / 60.0
        pickup_zone = pd.to_numeric(frame["PULocationID"], errors="coerce")
        dropoff_zone = pd.to_numeric(frame["DOLocationID"], errors="coerce")
        distance = pd.to_numeric(frame["trip_distance"], errors="coerce")
        valid = (
            duration.between(MIN_TRIP_MINUTES, MAX_TRIP_MINUTES)
            & distance.between(MIN_TRIP_MILES, MAX_TRIP_MILES)
            & pickup_zone.isin(centers)
            & dropoff_zone.isin(centers)
        )
        cleaned = pd.DataFrame(
            {
                "pickup_zone": pickup_zone[valid].astype(np.int16),
                "dropoff_zone": dropoff_zone[valid].astype(np.int16),
                "direct_minutes": duration[valid].astype(np.float32),
                "pickup_hour": frame.loc[valid, "tpep_pickup_datetime"].dt.hour.astype(np.int8),
            }
        )
        valid_rows += len(cleaned)
        hour_counts += np.bincount(cleaned["pickup_hour"].to_numpy(), minlength=24)
        selected = random.random(len(cleaned)) < sample_probability
        if selected.any():
            sample_frames.append(cleaned.loc[selected])

    sample = pd.concat(sample_frames, ignore_index=True)
    if len(sample) > TARGET_SAMPLE_ROWS:
        sample = sample.sample(TARGET_SAMPLE_ROWS, random_state=SAMPLE_SEED)
    pickup = np.asarray([centers[int(zone)] for zone in sample["pickup_zone"]], dtype=np.float64)
    dropoff = np.asarray([centers[int(zone)] for zone in sample["dropoff_zone"]], dtype=np.float64)
    direct_minutes = sample["direct_minutes"].to_numpy(dtype=np.float64)
    centroid_miles = np.linalg.norm(dropoff - pickup, axis=1)
    informative = centroid_miles > 0.25
    minutes_per_mile = float(np.median(direct_minutes[informative] / centroid_miles[informative]))
    return DemandProfile(
        hour_counts=hour_counts,
        pickup=pickup,
        dropoff=dropoff,
        direct_minutes=direct_minutes,
        pickup_hours=sample["pickup_hour"].to_numpy(dtype=np.int8),
        valid_rows=valid_rows,
        source_rows=source_rows,
        minutes_per_mile=minutes_per_mile,
    )


def save_profile(profile: DemandProfile, destination: Path) -> None:
    """추출 프로파일을 재현 가능한 압축 NumPy 파일에 저장한다."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        hour_counts=profile.hour_counts,
        pickup=profile.pickup,
        dropoff=profile.dropoff,
        direct_minutes=profile.direct_minutes,
        pickup_hours=profile.pickup_hours,
        valid_rows=np.asarray([profile.valid_rows]),
        source_rows=np.asarray([profile.source_rows]),
        minutes_per_mile=np.asarray([profile.minutes_per_mile]),
    )


def load_profile(path: Path) -> DemandProfile:
    """저장된 수요 프로파일을 불러온다."""
    with np.load(path) as data:
        return DemandProfile(
            hour_counts=data["hour_counts"],
            pickup=data["pickup"],
            dropoff=data["dropoff"],
            direct_minutes=data["direct_minutes"],
            pickup_hours=data["pickup_hours"],
            valid_rows=int(data["valid_rows"][0]),
            source_rows=int(data["source_rows"][0]),
            minutes_per_mile=float(data["minutes_per_mile"][0]),
        )


def profile_audit(profile: DemandProfile) -> dict[str, object]:
    """공개 결과에 기록할 원본 감사 수치를 반환한다."""
    return {
        "source_rows": profile.source_rows,
        "valid_rows": profile.valid_rows,
        "sample_rows": len(profile.direct_minutes),
        "peak_hour": int(np.argmax(profile.hour_counts)),
        "peak_share": float(profile.hour_counts.max() / profile.hour_counts.sum()),
        "median_direct_minutes": float(np.median(profile.direct_minutes)),
        "minutes_per_centroid_mile": profile.minutes_per_mile,
        "hour_counts": profile.hour_counts.tolist(),
    }
