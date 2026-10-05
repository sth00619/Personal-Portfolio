"""저장된 실측 결과가 WO-11 Ship Gate를 충족하는지 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "results" / "report.json"


def load_report() -> dict[str, object]:
    """커밋된 실험 보고서를 불러온다."""
    return json.loads(REPORT.read_text())


def test_three_solomon_instances_have_feasible_gap_measurements() -> None:
    """세 공식 인스턴스의 OR-Tools 해가 완전하고 실행 가능해야 한다."""
    benchmark = load_report()["benchmark"]
    assert len(benchmark) >= 3
    for record in benchmark:
        assert record["customers"] == 100
        assert record["ortools"]["feasible"]
        assert record["ortools"]["unserved"] == 0
        assert record["ortools"]["distance_gap_percent"] >= 0


def test_four_policies_include_repeated_confidence_intervals() -> None:
    """정책별 서비스 지표가 12회 반복과 95% 구간을 포함해야 한다."""
    summaries = load_report()["policy_comparison"]
    assert {row["policy"] for row in summaries} == {"fcfs", "nearest", "batch_bundle", "mip_batch"}
    for row in summaries:
        assert row["replications"] >= 12
        metric = row["mean_delivery_minutes"]
        assert metric["ci95_low"] < metric["mean"] < metric["ci95_high"]


def test_supply_sensitivity_and_dynamic_price_are_measured() -> None:
    """라이더 수와 가격 정책 Ship Gate의 모든 조건이 있어야 한다."""
    report = load_report()
    assert {row["riders"] for row in report["rider_sensitivity"]} == {10, 20, 30}
    assert {row["dynamic_price"] for row in report["dynamic_price"]} == {False, True}
