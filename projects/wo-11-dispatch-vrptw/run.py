"""WO-11 Solomon 검증과 TLC 기반 동적 배차 실험을 실행한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.demand import DemandProfile, extract_profile, load_profile, profile_audit, save_profile
from src.simulation import POLICIES, REPLICATIONS, SimulationConfig, simulate, summarize_replications
from src.solomon import BENCHMARK_BEST, benchmark_record, greedy_nearest, load_instance, locate_instance, solve_ortools

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
DEFAULT_RESULTS = ROOT / "results"
PROFILE_PATH = RAW / "demand_profile.npz"
SOLOMON_ROOT = RAW / "solomon"
TLC_PARQUET = RAW / "yellow_tripdata.parquet"
ZONE_SHAPEFILE = RAW / "taxi_zones" / "taxi_zones" / "taxi_zones.shp"
POLICY_RIDERS = 20
SENSITIVITY_RIDERS = (10, 20, 30)
PRICE_RIDERS = 10
BASE_SEED = 2_000
FIGURE_SIZE = (9, 5)


def json_ready(value: object) -> object:
    """경로와 NumPy 계열 값을 JSON 기록형으로 변환한다."""
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def run_benchmarks(search_seconds: int) -> list[dict[str, object]]:
    """세 Solomon 인스턴스에서 탐욕 기준선과 제한시간 탐색을 비교한다."""
    records: list[dict[str, object]] = []
    for name, (best_vehicles, _) in BENCHMARK_BEST.items():
        instance = load_instance(locate_instance(SOLOMON_ROOT, name))
        greedy = greedy_nearest(instance)
        optimized = solve_ortools(instance, best_vehicles, search_seconds)
        if not optimized.feasible:
            raise RuntimeError(f"{name} OR-Tools 해가 실행 가능하지 않습니다")
        records.append(benchmark_record(instance, greedy, optimized))
        print(f"{name}: greedy={greedy.distance:.2f}, OR-Tools={optimized.distance:.2f}", flush=True)
    return records


def repeated(profile: DemandProfile, configurations: list[SimulationConfig]) -> list[dict[str, object]]:
    """설정 목록을 순서대로 실행해 원시 반복 기록을 모은다."""
    records: list[dict[str, object]] = []
    for index, configuration in enumerate(configurations, start=1):
        records.append(simulate(profile, configuration))
        if index % REPLICATIONS == 0:
            print(f"simulation runs={index}/{len(configurations)}", flush=True)
    return records


def build_policy_configs(replications: int) -> list[SimulationConfig]:
    """네 정책에 동일한 반복 seed를 배정한다."""
    return [
        SimulationConfig(policy, POLICY_RIDERS, False, BASE_SEED + replication)
        for policy in POLICIES
        for replication in range(replications)
    ]


def build_sensitivity_configs(replications: int) -> list[SimulationConfig]:
    """MIP 배치 정책의 라이더 수 민감도 설정을 만든다."""
    return [
        SimulationConfig("mip_batch", riders, False, BASE_SEED + replication)
        for riders in SENSITIVITY_RIDERS
        for replication in range(replications)
    ]


def build_price_configs(replications: int) -> list[SimulationConfig]:
    """공급 부족 조건의 고정·동적 가격 설정을 만든다."""
    return [
        SimulationConfig("nearest", PRICE_RIDERS, dynamic_price, BASE_SEED + replication)
        for dynamic_price in (False, True)
        for replication in range(replications)
    ]


def flatten_summary(summaries: list[dict[str, object]]) -> pd.DataFrame:
    """중첩된 평균·신뢰구간 요약을 CSV용 평면 표로 변환한다."""
    rows: list[dict[str, object]] = []
    for summary in summaries:
        row: dict[str, object] = {}
        for key, value in summary.items():
            if isinstance(value, dict) and {"mean", "ci95_low", "ci95_high"}.issubset(value):
                row[f"{key}_mean"] = value["mean"]
                row[f"{key}_ci95_low"] = value["ci95_low"]
                row[f"{key}_ci95_high"] = value["ci95_high"]
            else:
                row[key] = value
        rows.append(row)
    return pd.DataFrame(rows)


def save_benchmark_table(records: list[dict[str, object]], destination: Path) -> None:
    """Solomon 중첩 결과를 비교 CSV로 저장한다."""
    rows: list[dict[str, object]] = []
    for record in records:
        row: dict[str, object] = {"instance": record["instance"], "customers": record["customers"]}
        for prefix in ("best_known", "greedy", "ortools"):
            for key, value in record[prefix].items():
                row[f"{prefix}_{key}"] = value
        rows.append(row)
    pd.DataFrame(rows).to_csv(destination, index=False)


def save_plots(policy: pd.DataFrame, sensitivity: pd.DataFrame, price: pd.DataFrame, results: Path) -> None:
    """정책 트레이드오프, 공급 민감도, 가격 효과 그림을 저장한다."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    ax.scatter(policy["distance_miles_mean"], policy["mean_delivery_minutes_mean"], s=80)
    for _, row in policy.iterrows():
        ax.annotate(row["policy"], (row["distance_miles_mean"], row["mean_delivery_minutes_mean"]), xytext=(5, 5), textcoords="offset points")
    ax.set(xlabel="Total rider distance (centroid miles)", ylabel="Mean delivery time (minutes)", title="Dispatch policy trade-off")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(results / "policy_tradeoff.png", dpi=180)
    plt.close(fig)

    sensitivity = sensitivity.sort_values("riders")
    fig, left = plt.subplots(figsize=FIGURE_SIZE)
    left.errorbar(
        sensitivity["riders"],
        sensitivity["mean_delivery_minutes_mean"],
        yerr=[
            sensitivity["mean_delivery_minutes_mean"] - sensitivity["mean_delivery_minutes_ci95_low"],
            sensitivity["mean_delivery_minutes_ci95_high"] - sensitivity["mean_delivery_minutes_mean"],
        ],
        marker="o",
        label="delivery time",
    )
    right = left.twinx()
    right.plot(sensitivity["riders"], 100 * sensitivity["unassigned_rate_mean"], color="tab:red", marker="s", label="unassigned")
    left.set(xlabel="Base riders", ylabel="Mean delivery time (minutes)", title="Service-level sensitivity to rider supply")
    right.set_ylabel("Unassigned orders (%)")
    left.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(results / "rider_sensitivity.png", dpi=180)
    plt.close(fig)

    labels = ["dynamic" if value else "fixed" for value in price["dynamic_price"]]
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE)
    axes[0].bar(labels, price["mean_demand_supply_pressure_mean"], color=["gray", "tab:blue"])
    axes[0].set(ylabel="Waiting orders / idle riders", title="Supply-demand pressure")
    axes[1].bar(labels, 100 * price["unassigned_rate_mean"], color=["gray", "tab:blue"])
    axes[1].set(ylabel="Unassigned orders (%)", title="Service loss")
    fig.tight_layout()
    fig.savefig(results / "dynamic_price.png", dpi=180)
    plt.close(fig)


def main() -> None:
    """전체 실험을 실행하고 표·그림·원시 근거를 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--replications", type=int, default=REPLICATIONS)
    parser.add_argument("--search-seconds", type=int, default=5)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)

    if not PROFILE_PATH.exists():
        profile = extract_profile(TLC_PARQUET, ZONE_SHAPEFILE)
        save_profile(profile, PROFILE_PATH)
    else:
        profile = load_profile(PROFILE_PATH)
    audit = profile_audit(profile)
    print(f"TLC rows={audit['source_rows']}, valid={audit['valid_rows']}, sampled={audit['sample_rows']}", flush=True)

    benchmarks = run_benchmarks(args.search_seconds)
    policy_raw = repeated(profile, build_policy_configs(args.replications))
    sensitivity_raw = repeated(profile, build_sensitivity_configs(args.replications))
    price_raw = repeated(profile, build_price_configs(args.replications))
    policy_summary = summarize_replications(policy_raw, ("policy", "riders", "dynamic_price"))
    sensitivity_summary = summarize_replications(sensitivity_raw, ("policy", "riders", "dynamic_price"))
    price_summary = summarize_replications(price_raw, ("policy", "riders", "dynamic_price"))

    policy_frame = flatten_summary(policy_summary)
    sensitivity_frame = flatten_summary(sensitivity_summary)
    price_frame = flatten_summary(price_summary)
    save_benchmark_table(benchmarks, args.results / "solomon_benchmark.csv")
    policy_frame.to_csv(args.results / "policy_comparison.csv", index=False)
    sensitivity_frame.to_csv(args.results / "rider_sensitivity.csv", index=False)
    price_frame.to_csv(args.results / "dynamic_price.csv", index=False)
    save_plots(policy_frame, sensitivity_frame, price_frame, args.results)
    report = {
        "data_audit": audit,
        "benchmark": benchmarks,
        "simulation_contract": {
            "replications": args.replications,
            "policy_riders": POLICY_RIDERS,
            "sensitivity_riders": SENSITIVITY_RIDERS,
            "price_riders": PRICE_RIDERS,
        },
        "policy_comparison": policy_summary,
        "rider_sensitivity": sensitivity_summary,
        "dynamic_price": price_summary,
        "raw_replications": {"policy": policy_raw, "sensitivity": sensitivity_raw, "dynamic_price": price_raw},
    }
    (args.results / "report.json").write_text(json.dumps(json_ready(report), ensure_ascii=False, indent=2) + "\n")
    print(policy_frame[["policy", "mean_delivery_minutes_mean", "utilization_mean", "unassigned_rate_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
