"""무작위 실험 기반 정책 평가의 핵심 불변식을 검증한다."""

from __future__ import annotations

import numpy as np
import pytest

from src.data import FEATURE_COLUMNS, DatasetSplit
from src.evaluation import evaluate_scores, model_implied_segments, selected_effect, top_fraction_mask
from src.models import balanced_class_transformation_indices


def test_post_treatment_exposure_is_not_a_model_feature() -> None:
    """배정 이후 노출 변수와 결과 변수가 특성 목록에 들어가지 않는다."""
    assert len(FEATURE_COLUMNS) == 12
    assert "exposure" not in FEATURE_COLUMNS
    assert "treatment" not in FEATURE_COLUMNS
    assert "conversion" not in FEATURE_COLUMNS


def test_selected_effect_uses_both_randomized_arms() -> None:
    """처치군과 대조군의 전환율 차이를 선택 인원으로 환산한다."""
    outcome = np.array([1, 1, 0, 0, 0, 1, 0, 0], dtype=np.uint8)
    treatment = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)
    result = selected_effect(outcome, treatment, np.ones(len(outcome), dtype=bool))
    assert result["treated_rate"] == 0.5
    assert result["control_rate"] == 0.25
    assert result["incremental_conversions"] == 2


def test_top_fraction_keeps_exact_budget_with_ties() -> None:
    """동점 점수에도 예산에 해당하는 행만 선택한다."""
    score = np.ones(10)
    assert top_fraction_mask(score).sum() == 2
    with pytest.raises(ValueError):
        top_fraction_mask(score, fraction=0)


def test_class_transformation_training_is_balanced() -> None:
    """치료군 85%의 원본 배정을 Class Transformation 학습에서는 1:1로 맞춘다."""
    treatment = np.array([1] * 85 + [0] * 15, dtype=np.uint8)
    indices = balanced_class_transformation_indices(treatment)
    assert len(indices) == 30
    assert treatment[indices].sum() == 15


def test_qini_rewards_true_uplift_ranking() -> None:
    """인공 RCT에서 효과가 큰 세그먼트 우선 정책의 Qini가 역순보다 높다."""
    random = np.random.default_rng(42)
    n = 20_000
    segment = random.integers(0, 2, n)
    treatment = random.integers(0, 2, n, dtype=np.uint8)
    probability = 0.05 + 0.2 * segment * treatment
    outcome = (random.random(n) < probability).astype(np.uint8)
    split = DatasetSplit(segment.reshape(-1, 1), outcome, treatment)
    scores = {"helpful_first": segment.astype(float), "reverse": -segment.astype(float)}
    result = evaluate_scores(split, scores)
    assert result["helpful_first"]["qini_auc"] > result["reverse"]["qini_auc"]


def test_segments_are_model_implied_proxies() -> None:
    """잠재결과 예측을 해석용 그룹으로 매핑한다."""
    p0 = np.array([0.01, 0.2, 0.02, 0.01])
    p1 = np.array([0.01, 0.21, 0.22, 0.0])
    result = model_implied_segments(p0, p1, reference_p0=0.1, reference_uplift=0.1)
    assert result.tolist() == ["lost_cause_like", "sure_thing_like", "persuadable_like", "sleeping_dog_like"]
