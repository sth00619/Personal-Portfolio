"""WO-10 RCT 감사, 업리프트 정책 비교, 그래프와 결과 파일 생성."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.data import DEFAULT_SAMPLE_FRACTION, FEATURE_COLUMNS, DatasetSplit, load_sample, split_sample
from src.evaluation import TARGET_FRACTION, curve_points, evaluate_scores, model_implied_segments, paired_policy_difference, selected_effect
from src.models import fit_models

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data" / "criteo-uplift-v2.1.csv.gz"
DEFAULT_RESULTS = ROOT / "results"
RANDOM_SEED = 42
PERSUADABLE_QUANTILE = 0.80
FEATURE_COUNT = 3
CURVE_SIZE = (10, 6)


def serializable(value: object) -> object:
    """NumPy 스칼라와 배열을 JSON에 기록 가능한 값으로 바꾼다."""
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def segment_report(x: np.ndarray, y: np.ndarray, treatment: np.ndarray, segments: np.ndarray) -> dict[str, object]:
    """모델 암시 세그먼트의 RCT 효과와 익명 피처 차이를 요약한다."""
    report: dict[str, object] = {}
    for name in np.unique(segments):
        mask = segments == name
        report[str(name)] = {"share": float(mask.mean()), **selected_effect(y, treatment, mask)}

    persuadable = segments == "persuadable_like"
    other = ~persuadable
    pooled = np.std(x, axis=0).astype(float)
    difference = (np.mean(x[persuadable], axis=0) - np.mean(x[other], axis=0)) / np.where(pooled > 0, pooled, 1)
    top_features = np.argsort(-np.abs(difference))[:FEATURE_COUNT]
    report["persuadable_feature_differences"] = [
        {
            "feature": FEATURE_COLUMNS[index],
            "standardized_difference": float(difference[index]),
            "segment_mean": float(np.mean(x[persuadable, index])),
            "other_mean": float(np.mean(x[other, index])),
        }
        for index in top_features
    ]
    return report


def save_qini_plot(test: DatasetSplit, scores: dict[str, np.ndarray], destination: Path) -> None:
    """보류 집합의 Qini 곡선과 무작위 순위 기준선을 저장한다."""
    fig, ax = plt.subplots(figsize=CURVE_SIZE)
    for name, score in scores.items():
        fraction, incremental = curve_points(test, score)
        ax.plot(fraction, incremental, label=name, linewidth=1.5)
    total_effect = selected_effect(test.y, test.treatment, np.ones(len(test.y), dtype=bool))["incremental_conversions"]
    ax.plot([0, 1], [0, total_effect], "k--", label="random targeting", linewidth=1)
    ax.axvline(TARGET_FRACTION, color="gray", alpha=0.45, linewidth=1)
    ax.set(xlabel="Targeted fraction", ylabel="Estimated incremental conversions", title="Held-out RCT Qini curves")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def main() -> None:
    """모델 비교를 실행하고 검증 가능한 수치와 그림을 남긴다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--fraction", type=float, default=DEFAULT_SAMPLE_FRACTION)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)

    sample, source_audit = load_sample(args.data, args.fraction, RANDOM_SEED)
    parts = split_sample(sample, source_audit, RANDOM_SEED)
    del sample
    print(f"Audited {parts.audit['source_rows']} source rows; fitting on {len(parts.train.y)} rows", flush=True)

    models = fit_models(parts.train)
    validation_scores = models.scores(parts.validation.x)
    validation_metrics = evaluate_scores(parts.validation, validation_scores)
    uplift_names = [name for name in validation_scores if name != "response"]
    best_uplift = max(uplift_names, key=lambda name: validation_metrics[name]["qini_auc"])
    print(f"Validation-selected uplift policy: {best_uplift}", flush=True)

    test_scores = models.scores(parts.test.x)
    test_metrics = evaluate_scores(parts.test, test_scores)
    p0_validation, p1_validation = models.potential_outcomes(parts.validation.x)
    p0_test, p1_test = models.potential_outcomes(parts.test.x)
    p0_cutoff = float(np.median(p0_validation))
    uplift_cutoff = float(np.quantile(p1_validation - p0_validation, PERSUADABLE_QUANTILE))
    segments = model_implied_segments(p0_test, p1_test, p0_cutoff, uplift_cutoff)

    response_count = test_metrics["response"]["top20"]["incremental_conversions"]
    best_count = test_metrics[best_uplift]["top20"]["incremental_conversions"]
    result = {
        "dataset": parts.audit,
        "model_config": {
            "class_transformation_balanced_rows": models.class_transform_rows,
            "uplift_tree_train_rows": models.uplift_tree_rows,
        },
        "validation": validation_metrics,
        "selected_uplift_policy": best_uplift,
        "test": test_metrics,
        "top20_incremental_conversions_uplift_minus_response": best_count - response_count,
        "top20_paired_policy_difference": paired_policy_difference(parts.test, test_scores[best_uplift], test_scores["response"]),
        "segment_thresholds_from_validation": {"p0_median": p0_cutoff, "uplift_p80": uplift_cutoff},
        "model_implied_segments": segment_report(parts.test.x, parts.test.y, parts.test.treatment, segments),
    }
    (args.results / "metrics.json").write_text(json.dumps(serializable(result), ensure_ascii=False, indent=2) + "\n")
    save_qini_plot(parts.test, test_scores, args.results / "qini_curve.png")
    print(json.dumps({"selected_uplift_policy": best_uplift, "test": test_metrics, "difference": best_count - response_count}, indent=2), flush=True)


if __name__ == "__main__":
    main()
