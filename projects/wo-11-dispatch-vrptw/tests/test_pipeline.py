"""VRPTW 실행 가능성과 동적 배차 측정 계약을 검증한다."""

from __future__ import annotations

import numpy as np

from src.demand import DemandProfile
from src.simulation import SimulationConfig, simulate, summarize_replications
from src.solomon import SolomonInstance, greedy_nearest, validate_routes


def toy_instance() -> SolomonInstance:
    """용량 때문에 두 경로가 필요한 작은 VRPTW를 만든다."""
    return SolomonInstance(
        name="toy",
        vehicle_count=3,
        capacity=2,
        customer_ids=np.arange(5),
        coordinates=np.asarray([[0, 0], [1, 0], [2, 0], [0, 1], [0, 2]], dtype=float),
        demands=np.asarray([0, 1, 1, 1, 1]),
        ready_times=np.zeros(5, dtype=int),
        due_times=np.full(5, 100, dtype=int),
        service_times=np.zeros(5, dtype=int),
    )


def synthetic_profile() -> DemandProfile:
    """테스트용 시간·공간 수요 분포를 만든다."""
    random = np.random.default_rng(7)
    rows = 2_000
    return DemandProfile(
        hour_counts=np.full(24, 100, dtype=int),
        pickup=random.normal(0, 1, size=(rows, 2)),
        dropoff=random.normal(0, 1, size=(rows, 2)),
        direct_minutes=np.full(rows, 8.0),
        pickup_hours=np.tile(np.arange(24), rows // 24 + 1)[:rows],
        valid_rows=rows,
        source_rows=rows,
        minutes_per_mile=3.0,
    )


def test_greedy_solution_obeys_capacity_and_visits_every_customer() -> None:
    """탐욕 기준선도 제약을 만족하는 완전한 경로만 반환한다."""
    solution = greedy_nearest(toy_instance())
    assert solution.feasible
    assert solution.unserved == 0
    assert solution.vehicles == 2
    assert solution.distance > 0


def test_route_validator_rejects_duplicate_and_missing_customer() -> None:
    """그럴듯한 거리라도 고객 중복·누락이 있으면 실패한다."""
    feasible, unserved = validate_routes(toy_instance(), [[0, 1, 2, 0], [0, 2, 3, 0]])
    assert not feasible
    assert unserved == 1


def test_simulation_returns_bounded_service_metrics() -> None:
    """이산사건 실행이 관측 주문과 서비스 지표를 생성한다."""
    result = simulate(synthetic_profile(), SimulationConfig("nearest", riders=12, seed=11))
    assert result["orders"] > 0
    assert 0 <= result["unassigned_rate"] <= 1
    assert result["mean_delivery_minutes"] > 0
    assert result["distance_miles"] > 0


def test_bundle_policy_records_real_bundles() -> None:
    """묶음 정책은 두 주문을 한 라이더 경로에 포함한 비율을 기록한다."""
    result = simulate(synthetic_profile(), SimulationConfig("batch_bundle", riders=12, seed=13))
    assert result["bundle_share"] > 0


def test_replication_summary_contains_nonzero_confidence_interval() -> None:
    """확률적 반복값은 평균 하나가 아니라 95% 구간으로 요약한다."""
    records = [
        simulate(synthetic_profile(), SimulationConfig("fcfs", riders=12, seed=seed))
        for seed in (20, 21, 22, 23)
    ]
    summary = summarize_replications(records, ("policy", "riders", "dynamic_price"))[0]
    interval = summary["mean_delivery_minutes"]
    assert interval["ci95_low"] < interval["mean"] < interval["ci95_high"]
