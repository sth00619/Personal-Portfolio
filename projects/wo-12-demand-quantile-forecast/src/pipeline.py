"""End-to-end walk-forward experiment for WO-12."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import PROJECT_DIR, ExperimentConfig
from .data import MIN_HISTORY, M5Subset, assign_intermittency, build_feature_frame, load_subset
from .metrics import (
    interval_coverage,
    mean_pinball_loss,
    pinball_loss,
    rearrange_quantiles,
    root_mean_squared_error,
)
from .modeling import (
    fit_point_model,
    fit_quantile_models,
    predict_point,
    predict_quantiles,
)


NOMINAL_COVERAGE = 0.8
PLOT_DPI = 160
FIGURE_SIZE = (8.0, 4.8)


def _portable_path(path: Path) -> str:
    """Prefer a project-relative path while preserving valid external overrides."""

    try:
        return str(path.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def fold_bounds(total_days: int, horizon: int, fold_count: int) -> list[tuple[int, int]]:
    """Return expanding-origin evaluation intervals ending at the final day."""

    if total_days < horizon * fold_count:
        raise ValueError("not enough observations for requested walk-forward folds")
    bounds: list[tuple[int, int]] = []
    for fold_index in range(fold_count):
        evaluation_end = total_days - horizon * (fold_count - fold_index - 1)
        evaluation_start = evaluation_end - horizon
        bounds.append((evaluation_start, evaluation_end))
    return bounds


def _fit_and_predict(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    config: ExperimentConfig,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Fit point and quantile models and return ordered predictions."""

    point_model = fit_point_model(train, config)
    quantile_models = fit_quantile_models(train, config.quantiles, config)
    point_prediction = predict_point(point_model, evaluation)
    raw_quantiles = predict_quantiles(quantile_models, evaluation, config.quantiles)
    quantile_prediction, crossing_rate = rearrange_quantiles(raw_quantiles)
    return point_prediction, quantile_prediction, crossing_rate


def _prediction_frame(
    evaluation: pd.DataFrame,
    point_prediction: np.ndarray,
    quantile_prediction: np.ndarray,
    quantiles: tuple[float, ...],
    fold: int,
) -> pd.DataFrame:
    """Combine identifiers, outcomes, and model predictions for evaluation."""

    output = evaluation[["item_id", "target_index", "target"]].copy()
    output = output.rename(columns={"target": "actual"})
    output["fold"] = fold
    output["point"] = point_prediction
    for column, quantile in enumerate(quantiles):
        output[f"q{int(quantile * 100):02d}"] = quantile_prediction[:, column]
    return output


def _metrics_for_frame(
    frame: pd.DataFrame,
    quantiles: tuple[float, ...],
    model: str,
    scope: str,
    segment: str,
    fold: int | str,
) -> dict[str, object]:
    """Compute comparison metrics for one prediction slice."""

    actual = frame["actual"].to_numpy(dtype=float)
    point = frame["point"].to_numpy(dtype=float)
    if model == "point_baseline":
        matrix = np.repeat(point[:, None], len(quantiles), axis=1)
        coverage = float("nan")
        covered = 0
    elif model == "quantile":
        matrix = frame[[f"q{int(q * 100):02d}" for q in quantiles]].to_numpy(dtype=float)
        coverage, covered, _ = interval_coverage(actual, matrix[:, 0], matrix[:, -1])
    else:
        raise ValueError(f"unknown model: {model}")
    return {
        "fold": fold,
        "scope": scope,
        "segment": segment,
        "model": model,
        "observations": int(len(frame)),
        "covered": covered,
        "coverage": coverage,
        "coverage_gap_pp": (coverage - NOMINAL_COVERAGE) * 100 if model == "quantile" else np.nan,
        "mean_pinball_loss": mean_pinball_loss(actual, matrix, quantiles),
        "rmse": root_mean_squared_error(actual, point if model == "point_baseline" else matrix[:, 1]),
    }


def _quantile_loss_rows(
    frame: pd.DataFrame,
    quantiles: tuple[float, ...],
    model: str,
    scope: str,
    segment: str,
) -> list[dict[str, object]]:
    """Return one explicit loss row per model quantile."""

    actual = frame["actual"].to_numpy(dtype=float)
    rows: list[dict[str, object]] = []
    for quantile in quantiles:
        prediction = (
            frame["point"].to_numpy(dtype=float)
            if model == "point_baseline"
            else frame[f"q{int(quantile * 100):02d}"].to_numpy(dtype=float)
        )
        rows.append(
            {
                "scope": scope,
                "segment": segment,
                "model": model,
                "quantile": quantile,
                "pinball_loss": pinball_loss(actual, prediction, quantile),
                "observations": int(len(frame)),
            }
        )
    return rows


def _plot_coverage(metrics: pd.DataFrame, destination: Path) -> None:
    """Plot empirical interval coverage for the requested Ship Gate slices."""

    selected = metrics.query("model == 'quantile'").copy()
    selected["label"] = selected["scope"] + " / " + selected["segment"]
    figure, axis = plt.subplots(figsize=FIGURE_SIZE)
    axis.bar(selected["label"], selected["coverage"] * 100, color="#2563eb")
    axis.axhline(NOMINAL_COVERAGE * 100, color="#dc2626", linestyle="--", label="nominal 80%")
    axis.set_ylabel("Empirical coverage (%)")
    axis.set_ylim(0, 100)
    axis.tick_params(axis="x", rotation=20)
    axis.legend()
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(figure)


def _plot_model_comparison(metrics: pd.DataFrame, destination: Path) -> None:
    """Plot the baseline and quantile mean pinball losses."""

    selected = metrics.query("scope == 'item' and segment == 'all'").copy()
    labels = selected["model"].replace(
        {"point_baseline": "point baseline", "quantile": "quantile models"}
    )
    figure, axis = plt.subplots(figsize=FIGURE_SIZE)
    axis.bar(labels, selected["mean_pinball_loss"], color=["#64748b", "#16a34a"])
    axis.set_ylabel("Mean pinball loss (lower is better)")
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(figure)


def run_experiment(config: ExperimentConfig) -> dict[str, object]:
    """Run all walk-forward folds, persist evidence tables, and return a summary."""

    config.results_dir.mkdir(parents=True, exist_ok=True)
    subset = load_subset(
        config.data_dir / "sales_train_evaluation.csv",
        config.data_dir / "calendar.csv",
        config.store_id,
        config.category_id,
        config.chunk_rows,
    )
    aggregate = M5Subset(
        item_ids=np.array([f"{config.store_id}_{config.category_id}"]),
        values=subset.values.sum(axis=0, keepdims=True),
        day_labels=subset.day_labels,
        calendar=subset.calendar,
    )
    item_predictions: list[pd.DataFrame] = []
    aggregate_predictions: list[pd.DataFrame] = []
    crossing_records: list[dict[str, object]] = []
    segment_profiles: list[pd.DataFrame] = []

    bounds = fold_bounds(len(subset.day_labels), config.horizon, config.fold_count)
    for fold, (evaluation_start, evaluation_end) in enumerate(bounds, start=1):
        train_start = max(MIN_HISTORY, evaluation_start - config.training_days)
        train_indices = np.arange(train_start, evaluation_start)
        evaluation_indices = np.arange(evaluation_start, evaluation_end)
        print(
            f"fold={fold} train_targets={train_start}:{evaluation_start} "
            f"evaluation_targets={evaluation_start}:{evaluation_end}",
            flush=True,
        )

        train = build_feature_frame(
            subset.values, subset.item_ids, subset.calendar, train_indices
        )
        evaluation = build_feature_frame(
            subset.values, subset.item_ids, subset.calendar, evaluation_indices
        )
        point, quantiles, crossing_rate = _fit_and_predict(train, evaluation, config)
        item_frame = _prediction_frame(
            evaluation, point, quantiles, config.quantiles, fold
        )
        segment_profile = assign_intermittency(
            subset.values,
            subset.item_ids,
            evaluation_start,
            config.intermittent_zero_threshold,
        )
        segment_profile["fold"] = fold
        segment_profiles.append(segment_profile)
        item_frame = item_frame.merge(segment_profile, on=["item_id", "fold"], how="left")
        item_predictions.append(item_frame)
        crossing_records.append(
            {"fold": fold, "scope": "item", "crossing_rate": crossing_rate}
        )

        aggregate_train = build_feature_frame(
            aggregate.values,
            aggregate.item_ids,
            aggregate.calendar,
            train_indices,
        )
        aggregate_evaluation = build_feature_frame(
            aggregate.values,
            aggregate.item_ids,
            aggregate.calendar,
            evaluation_indices,
        )
        aggregate_point, aggregate_quantiles, aggregate_crossing = _fit_and_predict(
            aggregate_train, aggregate_evaluation, config
        )
        aggregate_predictions.append(
            _prediction_frame(
                aggregate_evaluation,
                aggregate_point,
                aggregate_quantiles,
                config.quantiles,
                fold,
            )
        )
        crossing_records.append(
            {"fold": fold, "scope": "aggregate", "crossing_rate": aggregate_crossing}
        )

    item_all = pd.concat(item_predictions, ignore_index=True)
    aggregate_all = pd.concat(aggregate_predictions, ignore_index=True)

    metric_rows: list[dict[str, object]] = []
    quantile_rows: list[dict[str, object]] = []
    for model in ("point_baseline", "quantile"):
        metric_rows.append(
            _metrics_for_frame(item_all, config.quantiles, model, "item", "all", "all")
        )
        quantile_rows.extend(
            _quantile_loss_rows(item_all, config.quantiles, model, "item", "all")
        )
        for segment in ("intermittent", "regular"):
            segment_frame = item_all.loc[item_all["segment"] == segment]
            metric_rows.append(
                _metrics_for_frame(
                    segment_frame, config.quantiles, model, "item", segment, "all"
                )
            )
            quantile_rows.extend(
                _quantile_loss_rows(
                    segment_frame, config.quantiles, model, "item", segment
                )
            )
        metric_rows.append(
            _metrics_for_frame(
                aggregate_all, config.quantiles, model, "aggregate", "all", "all"
            )
        )
        quantile_rows.extend(
            _quantile_loss_rows(
                aggregate_all, config.quantiles, model, "aggregate", "all"
            )
        )

    fold_rows = [
        _metrics_for_frame(
            item_all.loc[item_all["fold"] == fold],
            config.quantiles,
            "quantile",
            "item",
            "all",
            fold,
        )
        for fold in range(1, config.fold_count + 1)
    ]
    metrics = pd.DataFrame.from_records(metric_rows)
    fold_metrics = pd.DataFrame.from_records(fold_rows)
    quantile_losses = pd.DataFrame.from_records(quantile_rows)
    crossings = pd.DataFrame.from_records(crossing_records)
    profiles = pd.concat(segment_profiles, ignore_index=True)

    metric_columns = [
        "scope",
        "segment",
        "model",
        "observations",
        "covered",
        "coverage",
        "coverage_gap_pp",
        "mean_pinball_loss",
        "rmse",
    ]
    metrics[metric_columns].to_csv(config.results_dir / "ship_gate_metrics.csv", index=False)
    fold_metrics.to_csv(config.results_dir / "fold_metrics.csv", index=False)
    quantile_losses.to_csv(config.results_dir / "quantile_losses.csv", index=False)
    crossings.to_csv(config.results_dir / "quantile_crossings.csv", index=False)
    profiles.groupby(["fold", "segment"], as_index=False).agg(
        items=("item_id", "nunique"),
        mean_zero_share=("zero_share", "mean"),
    ).to_csv(config.results_dir / "segment_profile.csv", index=False)

    coverage_plot_metrics = metrics.loc[
        (metrics["model"] == "quantile")
        & (
            ((metrics["scope"] == "item") & metrics["segment"].isin(["intermittent", "regular"]))
            | (metrics["scope"] == "aggregate")
        )
    ]
    _plot_coverage(coverage_plot_metrics, config.results_dir / "coverage_comparison.png")
    _plot_model_comparison(metrics, config.results_dir / "pinball_comparison.png")

    item_quantile = metrics.query(
        "scope == 'item' and segment == 'all' and model == 'quantile'"
    ).iloc[0]
    item_baseline = metrics.query(
        "scope == 'item' and segment == 'all' and model == 'point_baseline'"
    ).iloc[0]
    summary: dict[str, object] = {
        "config": {
            **asdict(config),
            "data_dir": _portable_path(config.data_dir),
            "results_dir": _portable_path(config.results_dir),
        },
        "dataset": {
            "items": int(len(subset.item_ids)),
            "days": int(len(subset.day_labels)),
            "store_id": config.store_id,
            "category_id": config.category_id,
            "evaluation_observations": int(len(item_all)),
        },
        "ship_gate": {
            "item_coverage": float(item_quantile["coverage"]),
            "item_coverage_numerator": int(item_quantile["covered"]),
            "item_coverage_denominator": int(item_quantile["observations"]),
            "coverage_gap_pp": float(item_quantile["coverage_gap_pp"]),
            "point_baseline_mean_pinball": float(item_baseline["mean_pinball_loss"]),
            "quantile_mean_pinball": float(item_quantile["mean_pinball_loss"]),
            "pinball_improvement_percent": float(
                (item_baseline["mean_pinball_loss"] - item_quantile["mean_pinball_loss"])
                / item_baseline["mean_pinball_loss"]
                * 100
            ),
        },
    }
    (config.results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary
