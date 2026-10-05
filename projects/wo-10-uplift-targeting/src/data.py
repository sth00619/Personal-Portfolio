"""수정본 Criteo RCT를 감사하고 재현 가능한 표본·분할을 만든다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = tuple(f"f{index}" for index in range(12))
INDICATOR_COLUMNS = ("treatment", "conversion", "visit", "exposure")
ALL_COLUMNS = FEATURE_COLUMNS + INDICATOR_COLUMNS
EXPECTED_SOURCE_ROWS = 13_979_592
CHUNK_ROWS = 250_000
DEFAULT_SAMPLE_FRACTION = 0.10
DEFAULT_SEED = 42
TEST_FRACTION = 0.20
VALIDATION_FRACTION_OF_REMAINDER = 0.25


@dataclass(frozen=True)
class DatasetSplit:
    """동일한 피처 처리 규칙을 적용한 한 평가 구간."""

    x: np.ndarray
    y: np.ndarray
    treatment: np.ndarray


@dataclass(frozen=True)
class SplitCollection:
    """학습·검증·최종 평가 구간과 감사 수치."""

    train: DatasetSplit
    validation: DatasetSplit
    test: DatasetSplit
    audit: dict[str, object]


def load_sample(path: Path, fraction: float = DEFAULT_SAMPLE_FRACTION, seed: int = DEFAULT_SEED) -> tuple[pd.DataFrame, dict[str, object]]:
    """원본을 전량 스캔하면서 레이블과 무관하게 행을 표본화한다."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("표본 비율은 0보다 크고 1 이하여야 합니다")
    if not path.is_file():
        raise FileNotFoundError(path)

    dtype = {name: "float32" for name in FEATURE_COLUMNS}
    dtype.update({name: "uint8" for name in INDICATOR_COLUMNS})
    random = np.random.default_rng(seed)
    sample_parts: list[pd.DataFrame] = []
    rows = treated = conversions = visits = exposures = control_exposures = 0
    columns_checked = False

    for chunk in pd.read_csv(path, compression="gzip", dtype=dtype, chunksize=CHUNK_ROWS):
        if not columns_checked:
            if tuple(chunk.columns) != ALL_COLUMNS:
                raise ValueError(f"예상과 다른 원본 열: {tuple(chunk.columns)}")
            columns_checked = True
        if not chunk[list(INDICATOR_COLUMNS)].isin((0, 1)).all().all():
            raise ValueError("처치와 라벨 열에 이진값 이외의 값이 있습니다")
        rows += len(chunk)
        treated += int(chunk["treatment"].sum())
        conversions += int(chunk["conversion"].sum())
        visits += int(chunk["visit"].sum())
        exposures += int(chunk["exposure"].sum())
        control_exposures += int(chunk.loc[chunk["treatment"] == 0, "exposure"].sum())

        # 표본 선택은 원본 행 순서에 대한 난수만 사용한다. 처치·결과를 보지 않는다.
        selected = random.random(len(chunk)) < fraction
        if selected.any():
            sample_parts.append(chunk.loc[selected].copy())

    if rows != EXPECTED_SOURCE_ROWS:
        raise ValueError(f"수정본 원본 행 수가 다릅니다: {rows}")
    sample = pd.concat(sample_parts, ignore_index=True)
    audit: dict[str, object] = {
        "source_rows": rows,
        "source_treated": treated,
        "source_control": rows - treated,
        "source_conversions": conversions,
        "source_visits": visits,
        "source_exposures": exposures,
        "source_control_exposures": control_exposures,
        "sample_rows": len(sample),
        "sample_treated": int(sample["treatment"].sum()),
        "sample_conversions": int(sample["conversion"].sum()),
        "sample_fraction_requested": fraction,
        "sample_seed": seed,
    }
    return sample, audit


def split_sample(sample: pd.DataFrame, audit: dict[str, object], seed: int = DEFAULT_SEED) -> SplitCollection:
    """처치·희소 전환 라벨을 보존하며 60/20/20 구간을 분리한다."""
    labels = sample["treatment"].to_numpy(dtype=np.uint8) * 2 + sample["conversion"].to_numpy(dtype=np.uint8)
    all_indices = np.arange(len(sample))
    remainder, test_indices = train_test_split(
        all_indices, test_size=TEST_FRACTION, random_state=seed, stratify=labels
    )
    train_indices, validation_indices = train_test_split(
        remainder,
        test_size=VALIDATION_FRACTION_OF_REMAINDER,
        random_state=seed + 1,
        stratify=labels[remainder],
    )

    features = sample.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=np.float32)
    train_medians = np.nanmedian(features[train_indices], axis=0)
    if not np.isfinite(train_medians).all():
        raise ValueError("학습 구간에서 중앙값을 계산할 수 없는 피처가 있습니다")
    features = np.where(np.isfinite(features), features, train_medians).astype(np.float32)
    outcome = sample["conversion"].to_numpy(dtype=np.uint8)
    treatment = sample["treatment"].to_numpy(dtype=np.uint8)

    def build(indices: np.ndarray) -> DatasetSplit:
        """한 구간의 피처·처치·전환을 분리한다."""
        return DatasetSplit(features[indices], outcome[indices], treatment[indices])

    train = build(train_indices)
    validation = build(validation_indices)
    test = build(test_indices)
    audit = dict(audit)
    audit["splits"] = {
        name: {
            "rows": len(part.y),
            "treated": int(part.treatment.sum()),
            "control": int(len(part.y) - part.treatment.sum()),
            "conversions": int(part.y.sum()),
        }
        for name, part in (("train", train), ("validation", validation), ("test", test))
    }
    audit["max_abs_standardized_mean_difference"] = float(max_abs_smd(features, treatment))
    audit["feature_missing_values_before_imputation"] = int(sample.loc[:, list(FEATURE_COLUMNS)].isna().sum().sum())
    return SplitCollection(train, validation, test, audit)


def max_abs_smd(features: np.ndarray, treatment: np.ndarray) -> float:
    """표본의 처치군·대조군 피처별 표준화 평균 차이의 최대값을 계산한다."""
    treated = features[treatment == 1].astype(np.float64)
    control = features[treatment == 0].astype(np.float64)
    pooled_sd = np.sqrt((treated.var(axis=0) + control.var(axis=0)) / 2.0)
    difference = np.abs(treated.mean(axis=0) - control.mean(axis=0))
    smd = np.divide(difference, pooled_sd, out=np.zeros_like(difference), where=pooled_sd > 0)
    return float(smd.max())
