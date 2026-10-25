"""End-to-end WO-13 temporal fraud detection experiment."""

from __future__ import annotations

import gc
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import PROJECT_DIR, ExperimentConfig
from .data import (
    encode_split,
    feature_columns,
    high_missing_columns,
    load_joined_data,
    make_splits,
    temporal_inner_split,
)
from .metrics import ranking_metrics, select_cost_threshold, threshold_sweep
from .modeling import fit_model, measure_latency, predict_probabilities


VALIDATION_THRESHOLDS = tuple(np.round(np.arange(0.01, 1.0, 0.01), 2))
REPORT_THRESHOLDS = (0.01, 0.03, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
DEFAULT_THRESHOLD = 0.5
PLOT_DPI = 160
FIGURE_SIZE = (8.0, 4.8)


def _portable_path(path: Path) -> str:
    """Prefer a project-relative path for committed result metadata."""

    try:
        return str(path.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def _fit_ranking_experiment(
    frame: pd.DataFrame,
    train_indices: np.ndarray,
    test_indices: np.ndarray,
    features: list[str],
    config: ExperimentConfig,
) -> tuple[dict[str, float], np.ndarray]:
    """Fit one split-feature experiment and return ranking metrics and scores."""

    split = encode_split(
        frame,
        train_indices,
        test_indices,
        features,
        config.target_column,
    )
    model = fit_model(split, config)
    probabilities = predict_probabilities(model, split.x_test)
    metrics = ranking_metrics(split.y_test, probabilities)
    del split, model
    gc.collect()
    return metrics, probabilities


def _plot_split_comparison(frame: pd.DataFrame, destination: Path) -> None:
    """Plot PR-AUC and ROC-AUC for temporal and random holdouts."""

    pivot = frame.pivot(index="split", columns="metric", values="value")
    axis = pivot[["pr_auc", "roc_auc"]].plot.bar(
        figsize=FIGURE_SIZE,
        color=["#2563eb", "#64748b"],
    )
    axis.set_ylabel("Area under curve")
    axis.set_ylim(0, 1)
    axis.set_xlabel("")
    axis.tick_params(axis="x", rotation=0)
    axis.legend(["PR-AUC", "ROC-AUC"])
    axis.figure.tight_layout()
    axis.figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(axis.figure)


def _plot_missing_ablation(frame: pd.DataFrame, destination: Path) -> None:
    """Plot temporal metrics with high-missing features included and removed."""

    pivot = frame.pivot(index="feature_policy", columns="metric", values="value")
    pivot = pivot.rename(
        index={
            "drop_gt_90pct_missing": "drop >90% missing",
            "include_all": "include all",
        }
    )
    axis = pivot[["pr_auc", "roc_auc"]].plot.bar(
        figsize=FIGURE_SIZE,
        color=["#16a34a", "#94a3b8"],
    )
    axis.set_ylabel("Area under curve")
    axis.set_ylim(0, 1)
    axis.set_xlabel("")
    axis.tick_params(axis="x", rotation=0)
    axis.legend(["PR-AUC", "ROC-AUC"])
    axis.figure.tight_layout()
    axis.figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(axis.figure)


def _plot_threshold_tradeoff(frame: pd.DataFrame, destination: Path) -> None:
    """Plot precision, recall, and normalized assumed cost across thresholds."""

    figure, rate_axis = plt.subplots(figsize=FIGURE_SIZE)
    cost_axis = rate_axis.twinx()
    rate_axis.plot(frame["threshold"], frame["precision"], label="precision", color="#2563eb")
    rate_axis.plot(frame["threshold"], frame["recall"], label="recall", color="#16a34a")
    cost_axis.plot(
        frame["threshold"],
        frame["cost_per_transaction"],
        label="assumed cost / transaction",
        color="#dc2626",
        linestyle="--",
    )
    selected = frame.loc[frame["selected_on_validation"]]
    if not selected.empty:
        rate_axis.axvline(
            float(selected.iloc[0]["threshold"]),
            color="#111827",
            linestyle=":",
            label="validation-selected threshold",
        )
    rate_axis.set_xlabel("Decision threshold")
    rate_axis.set_ylabel("Precision / recall")
    cost_axis.set_ylabel("Assumed cost per transaction")
    lines = rate_axis.lines + cost_axis.lines
    rate_axis.legend(lines, [line.get_label() for line in lines], loc="center right")
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(figure)


def _long_metric_rows(
    experiment: str,
    split: str,
    feature_policy: str,
    metrics: dict[str, float],
    observations: int,
) -> list[dict[str, object]]:
    """Convert a ranking metric dictionary into a tidy evidence table."""

    return [
        {
            "experiment": experiment,
            "split": split,
            "feature_policy": feature_policy,
            "metric": metric,
            "value": value,
            "observations": observations,
        }
        for metric, value in metrics.items()
    ]


def run_experiment(config: ExperimentConfig) -> dict[str, object]:
    """Run every Ship Gate comparison and persist measured evidence."""

    config.results_dir.mkdir(parents=True, exist_ok=True)
    frame = load_joined_data(
        config.data_dir / "train_transaction.csv",
        config.data_dir / "train_identity.csv",
    )
    features_all = feature_columns(frame, config.id_column, config.target_column)
    splits = make_splits(
        frame,
        config.target_column,
        config.time_column,
        config.train_fraction,
        config.random_seed,
    )
    missing_rates = high_missing_columns(
        frame,
        splits.time_train,
        features_all,
        config.missing_threshold,
    )
    high_missing = set(missing_rates.index)
    features_drop = [column for column in features_all if column not in high_missing]
    missing_rates.rename("missing_rate").to_csv(
        config.results_dir / "high_missing_features.csv",
        header=True,
    )

    inner_train, threshold_validation = temporal_inner_split(
        splits.time_train, config.inner_train_fraction
    )
    print(
        f"threshold validation fit={len(inner_train)} validation={len(threshold_validation)}",
        flush=True,
    )
    validation_split = encode_split(
        frame,
        inner_train,
        threshold_validation,
        features_drop,
        config.target_column,
    )
    validation_model = fit_model(validation_split, config)
    validation_probabilities = predict_probabilities(
        validation_model, validation_split.x_test
    )
    selected_threshold, validation_sweep = select_cost_threshold(
        validation_split.y_test,
        validation_probabilities,
        VALIDATION_THRESHOLDS,
        config.false_positive_cost,
        config.false_negative_cost,
    )
    validation_sweep.to_csv(
        config.results_dir / "validation_threshold_sweep.csv", index=False
    )
    del validation_split, validation_model, validation_probabilities
    gc.collect()

    print(f"temporal all-feature model features={len(features_all)}", flush=True)
    time_all_metrics, _ = _fit_ranking_experiment(
        frame,
        splits.time_train,
        splits.time_test,
        features_all,
        config,
    )

    print(f"random reduced-feature model features={len(features_drop)}", flush=True)
    random_metrics, _ = _fit_ranking_experiment(
        frame,
        splits.random_train,
        splits.random_test,
        features_drop,
        config,
    )

    print(f"temporal reduced-feature model features={len(features_drop)}", flush=True)
    time_split = encode_split(
        frame,
        splits.time_train,
        splits.time_test,
        features_drop,
        config.target_column,
    )
    time_model = fit_model(time_split, config)
    time_probabilities = predict_probabilities(time_model, time_split.x_test)
    time_metrics = ranking_metrics(time_split.y_test, time_probabilities)

    ranking_rows = [
        *_long_metric_rows(
            "split_comparison",
            "temporal",
            "drop_gt_90pct_missing",
            time_metrics,
            len(splits.time_test),
        ),
        *_long_metric_rows(
            "split_comparison",
            "random",
            "drop_gt_90pct_missing",
            random_metrics,
            len(splits.random_test),
        ),
        *_long_metric_rows(
            "missing_ablation",
            "temporal",
            "include_all",
            time_all_metrics,
            len(splits.time_test),
        ),
        *_long_metric_rows(
            "missing_ablation",
            "temporal",
            "drop_gt_90pct_missing",
            time_metrics,
            len(splits.time_test),
        ),
    ]
    ranking_frame = pd.DataFrame.from_records(ranking_rows)
    ranking_frame.to_csv(config.results_dir / "ranking_metrics.csv", index=False)

    report_thresholds = (*REPORT_THRESHOLDS, selected_threshold)
    test_sweep = threshold_sweep(
        time_split.y_test,
        time_probabilities,
        report_thresholds,
        config.false_positive_cost,
        config.false_negative_cost,
    )
    test_sweep["selected_on_validation"] = np.isclose(
        test_sweep["threshold"], selected_threshold
    )
    test_sweep["default_threshold"] = np.isclose(
        test_sweep["threshold"], DEFAULT_THRESHOLD
    )
    test_sweep.to_csv(config.results_dir / "threshold_sweep.csv", index=False)

    default_row = test_sweep.loc[test_sweep["default_threshold"]].iloc[0]
    selected_row = test_sweep.loc[test_sweep["selected_on_validation"]].iloc[0]
    cost_saving_percent = float(
        (default_row["total_cost"] - selected_row["total_cost"])
        / default_row["total_cost"]
        * 100
    )
    latency = measure_latency(
        time_model,
        time_split.x_test,
        config.latency_samples,
        config.random_seed,
    )
    (config.results_dir / "latency.json").write_text(
        json.dumps(latency, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    importance = pd.DataFrame(
        {
            "feature": time_split.x_train.columns,
            "gain": time_model.booster_.feature_importance(importance_type="gain"),
            "split_count": time_model.booster_.feature_importance(importance_type="split"),
        }
    ).sort_values("gain", ascending=False)
    importance.to_csv(config.results_dir / "feature_importance.csv", index=False)

    split_plot = ranking_frame.query("experiment == 'split_comparison'")
    missing_plot = ranking_frame.query("experiment == 'missing_ablation'")
    _plot_split_comparison(split_plot, config.results_dir / "split_comparison.png")
    _plot_missing_ablation(missing_plot, config.results_dir / "missing_ablation.png")
    _plot_threshold_tradeoff(test_sweep, config.results_dir / "threshold_tradeoff.png")

    fraud_count = int(frame[config.target_column].sum())
    dataset_rows = int(len(frame))
    time_pr_gap_pp = float((random_metrics["pr_auc"] - time_metrics["pr_auc"]) * 100)
    missing_pr_delta_pp = float((time_metrics["pr_auc"] - time_all_metrics["pr_auc"]) * 100)
    summary: dict[str, object] = {
        "config": {
            **asdict(config),
            "data_dir": _portable_path(config.data_dir),
            "results_dir": _portable_path(config.results_dir),
        },
        "dataset": {
            "rows": dataset_rows,
            "fraud_count": fraud_count,
            "fraud_rate": fraud_count / dataset_rows,
            "joined_columns": int(frame.shape[1]),
            "predictor_count": int(len(features_all)),
            "high_missing_feature_count": int(len(high_missing)),
            "retained_feature_count": int(len(features_drop)),
            "time_train_rows": int(len(splits.time_train)),
            "time_test_rows": int(len(splits.time_test)),
        },
        "ship_gate": {
            "temporal_pr_auc": time_metrics["pr_auc"],
            "temporal_roc_auc": time_metrics["roc_auc"],
            "random_pr_auc": random_metrics["pr_auc"],
            "random_roc_auc": random_metrics["roc_auc"],
            "random_minus_temporal_pr_auc_pp": time_pr_gap_pp,
            "include_high_missing_pr_auc": time_all_metrics["pr_auc"],
            "drop_high_missing_pr_auc": time_metrics["pr_auc"],
            "drop_minus_include_pr_auc_pp": missing_pr_delta_pp,
            "selected_threshold": selected_threshold,
            "selected_threshold_source": "chronological validation inside training window",
            "false_positive_cost": config.false_positive_cost,
            "false_negative_cost": config.false_negative_cost,
            "default_threshold_cost": float(default_row["total_cost"]),
            "selected_threshold_cost": float(selected_row["total_cost"]),
            "cost_saving_percent": cost_saving_percent,
            "selected_precision": float(selected_row["precision"]),
            "selected_recall": float(selected_row["recall"]),
            "selected_false_positives": int(selected_row["fp"]),
            "selected_false_negatives": int(selected_row["fn"]),
        },
        "latency": latency,
    }
    (config.results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary

