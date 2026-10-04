"""Write measured machine-readable and visual experiment results."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt


MODEL_NAMES = ("baseline", "platt", "isotonic")
MODEL_LABELS = {
    "baseline": "LightGBM baseline",
    "platt": "Platt scaling",
    "isotonic": "Isotonic regression",
}
CURVE_FIGURE_SIZE = (7, 6)


def validate_result_contract(result: dict[str, object]) -> None:
    """Reject missing Ship Gate metrics or overlapping temporal partitions."""
    split = result["split"]
    train_days = tuple(split["train"]["days"])
    calibration_day = split["calibration"]["days"][0]
    test_day = split["test"]["days"][0]
    days = (*train_days, calibration_day, test_day)
    if tuple(sorted(days)) != days or len(set(days)) != len(days):
        raise ValueError("Split days overlap or are out of order")
    test_count = split["test"]["rows"]
    if set(result["metrics"]) != set(MODEL_NAMES):
        raise ValueError("Missing comparison model")
    for name in MODEL_NAMES:
        metrics = result["metrics"][name]
        if not {"auc", "log_loss", "ece", "sample_count"} <= set(metrics):
            raise ValueError(f"Missing Ship Gate metric: {name}")
        if metrics["sample_count"] != test_count:
            raise ValueError(f"Different test sample count: {name}")
        if not all(math.isfinite(metrics[key]) for key in ("auc", "log_loss", "ece")):
            raise ValueError(f"Nonfinite Ship Gate metric: {name}")
        if name not in result["bidding_proxy"] or name not in result["calibration_bins"]:
            raise ValueError(f"Missing proxy or curve: {name}")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    """Write a stable CSV table."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_curve(result: dict[str, object], path: Path) -> None:
    """Plot calibration curves for all models on the same test partition."""
    figure, axis = plt.subplots(figsize=CURVE_FIGURE_SIZE)
    curves = result["plot_curve"]["models"]
    upper = max(
        max(bucket["mean_prediction"], bucket["observed_rate"])
        for name in MODEL_NAMES
        for bucket in curves[name]
    ) * 1.08
    axis.plot([0, upper], [0, upper], linestyle="--", color="gray", label="Perfect calibration")
    for name in MODEL_NAMES:
        axis.plot(
            [bucket["mean_prediction"] for bucket in curves[name]],
            [bucket["observed_rate"] for bucket in curves[name]],
            marker="o",
            markersize=3,
            label=MODEL_LABELS[name],
        )
    axis.set(
        xlabel="Mean predicted CTR",
        ylabel="Observed click rate",
        title="Equal-count calibration curve (20 bins)",
        xlim=(0, upper),
        ylim=(0, upper),
    )
    axis.legend()
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_results(result: dict[str, object], output_dir: Path) -> None:
    """Persist JSON, CSV, figure, and a concise measured report."""
    validate_result_contract(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "experiment.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    metric_rows = [
        {"model": name, **result["metrics"][name]} for name in MODEL_NAMES
    ]
    write_csv(
        output_dir / "metrics.csv",
        ["model", "auc", "log_loss", "ece", "sample_count"],
        metric_rows,
    )
    bidding_rows = [
        {"model": name, **result["bidding_proxy"][name]} for name in MODEL_NAMES
    ]
    write_csv(
        output_dir / "bidding_analysis.csv",
        ["model", *result["bidding_proxy"]["baseline"].keys()],
        bidding_rows,
    )
    plot_curve(result, output_dir / "calibration_curve.png")
    metric_lines = [
        f"| {MODEL_LABELS[name]} | {result['metrics'][name]['auc']:.6f} | "
        f"{result['metrics'][name]['log_loss']:.6f} | {result['metrics'][name]['ece']:.6f} |"
        for name in MODEL_NAMES
    ]
    proxy_lines = [
        f"| {MODEL_LABELS[name]} | {result['bidding_proxy'][name]['aggregate_bias_krw']:.2f} | "
        f"{result['bidding_proxy'][name]['absolute_error_proxy_krw']:.2f} |"
        for name in MODEL_NAMES
    ]
    report = "\n".join(
        [
            "# 측정 보고서",
            "",
            "날짜가 다른 네 Parquet 조각에서 각 40,000행만 사용한 부분 표본 결과다.",
            "",
            "| 모델 | AUC | LogLoss | ECE (10 bins) |",
            "|---|---:|---:|---:|",
            *metric_lines,
            "",
            "| 모델 | 가상 입찰 집계 편향 (KRW) | 절대 추정 오차 proxy (KRW) |",
            "|---|---:|---:|",
            *proxy_lines,
            "",
            "가상 입찰가 = 1,000 KRW × 예측 CTR. 이 표는 실제 낙찰가나 광고비를 측정하지 않는다.",
            "원본 라벨은 비대칭 부분 표본화되어 있어 실제 트래픽 CTR로 해석할 수 없다.",
        ]
    )
    (output_dir / "report.md").write_text(report + "\n", encoding="utf-8")
