"""보류 RCT에서 순위 정책의 Qini와 증분 전환을 비교한다."""

from __future__ import annotations

import numpy as np
from sklift.metrics import qini_auc_score, qini_curve, uplift_auc_score

from src.data import DatasetSplit

TARGET_FRACTION = 0.20
RANDOM_BASELINE_QINI = 0.0
CONVERSION_VALUE = 1.0
TREATMENT_COST = 0.001
BOOTSTRAP_REPLICATES = 200
BOOTSTRAP_SEED = 1729


def selected_effect(y: np.ndarray, treatment: np.ndarray, selected: np.ndarray) -> dict[str, float | int]:
    """선택 구간의 무작위 배정군별 전환율 차이를 전체 선택 인원으로 환산한다."""
    treated_y = y[selected & (treatment == 1)]
    control_y = y[selected & (treatment == 0)]
    if len(treated_y) == 0 or len(control_y) == 0:
        raise ValueError("선택 구간에 두 무작위 배정군이 모두 있어야 합니다")
    p1 = float(treated_y.mean())
    p0 = float(control_y.mean())
    n = int(selected.sum())
    standard_error = float(np.sqrt(p1 * (1 - p1) / len(treated_y) + p0 * (1 - p0) / len(control_y)))
    return {
        "selected": n,
        "treated": len(treated_y),
        "control": len(control_y),
        "treated_rate": p1,
        "control_rate": p0,
        "uplift_rate": p1 - p0,
        "incremental_conversions": n * (p1 - p0),
        "ci95_low": n * ((p1 - p0) - 1.96 * standard_error),
        "ci95_high": n * ((p1 - p0) + 1.96 * standard_error),
        "net_value_proxy": n * ((p1 - p0) * CONVERSION_VALUE - TREATMENT_COST),
    }


def top_fraction_mask(score: np.ndarray, fraction: float = TARGET_FRACTION) -> np.ndarray:
    """동점이어도 정확히 지정 비율의 행을 선택한다."""
    if not 0 < fraction <= 1:
        raise ValueError("타기팅 비율은 0보다 크고 1 이하여야 합니다")
    count = max(1, int(np.ceil(len(score) * fraction)))
    chosen = np.argsort(-score, kind="stable")[:count]
    mask = np.zeros(len(score), dtype=bool)
    mask[chosen] = True
    return mask


def evaluate_scores(split: DatasetSplit, scores: dict[str, np.ndarray]) -> dict[str, dict[str, object]]:
    """모든 정책을 같은 테스트 결과와 타기팅 예산에서 비교한다."""
    report: dict[str, dict[str, object]] = {}
    # sklift의 perfect_qini_curve는 uint8 입력에서 산술 오버플로를 일으킨다.
    metric_y = split.y.astype(np.int64)
    metric_treatment = split.treatment.astype(np.int64)
    for name, score in scores.items():
        if len(score) != len(split.y) or not np.isfinite(score).all():
            raise ValueError(f"{name} 점수가 평가 데이터와 맞지 않습니다")
        mask = top_fraction_mask(score)
        report[name] = {
            "qini_auc": float(qini_auc_score(metric_y, score, metric_treatment)),
            "uplift_auc": float(uplift_auc_score(metric_y, score, metric_treatment)),
            "top20": selected_effect(split.y, split.treatment, mask),
        }
    return report


def paired_policy_difference(
    split: DatasetSplit, uplift_score: np.ndarray, response_score: np.ndarray
) -> dict[str, float | list[float]]:
    """같은 RCT 행을 재표본화해 상위 20% 정책 간 증분 전환 차이를 추정한다."""
    uplift_mask = top_fraction_mask(uplift_score)
    response_mask = top_fraction_mask(response_score)
    selected_count = int(uplift_mask.sum())
    point = selected_effect(split.y, split.treatment, uplift_mask)["uplift_rate"]
    point -= selected_effect(split.y, split.treatment, response_mask)["uplift_rate"]
    random = np.random.default_rng(BOOTSTRAP_SEED)
    estimates = np.empty(BOOTSTRAP_REPLICATES, dtype=float)

    def weighted_rate(weights: np.ndarray, mask: np.ndarray, arm: int) -> float:
        """부트스트랩 가중치로 해당 정책의 처치군 또는 대조군 전환율을 계산한다."""
        chosen = mask & (split.treatment == arm)
        return float(np.dot(weights[chosen], split.y[chosen]) / weights[chosen].sum())

    for iteration in range(BOOTSTRAP_REPLICATES):
        weights = random.poisson(1, size=len(split.y)).astype(np.float64)
        uplift_rate = weighted_rate(weights, uplift_mask, 1) - weighted_rate(weights, uplift_mask, 0)
        response_rate = weighted_rate(weights, response_mask, 1) - weighted_rate(weights, response_mask, 0)
        estimates[iteration] = selected_count * (uplift_rate - response_rate)
    return {
        "difference": selected_count * point,
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
        "method": "paired Poisson bootstrap over held-out rows",
    }


def curve_points(split: DatasetSplit, score: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """라이브러리 Qini 곡선을 행 비율·증분 전환으로 반환한다."""
    x, y = qini_curve(split.y.astype(np.int64), score, split.treatment.astype(np.int64))
    return x / len(split.y), y


def model_implied_segments(p0: np.ndarray, p1: np.ndarray, reference_p0: float, reference_uplift: float) -> np.ndarray:
    """모델 예측치로 해석용 네 그룹을 배정한다. 개인 인과 유형의 정답은 아니다."""
    uplift = p1 - p0
    segments = np.full(len(p0), "lost_cause_like", dtype="<U20")
    segments[p0 >= reference_p0] = "sure_thing_like"
    segments[uplift < 0] = "sleeping_dog_like"
    segments[uplift >= reference_uplift] = "persuadable_like"
    return segments
