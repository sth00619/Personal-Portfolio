"""End-to-end multi-table credit stability experiment."""

from __future__ import annotations

import gc
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import ExperimentConfig
from .data import (
    aggregate_bureau,
    aggregate_previous,
    encode_train_comparison,
    join_related_tables,
    load_application,
    make_proxy_order_split,
)
from .modeling import evaluate_model, feature_importance_table, fit_model
from .stability import feature_psi_table, summarize_psi


PLOT_DPI = 160
FIGURE_SIZE = (8.0, 4.8)
VARIANT_LABELS = {
    "baseline_application": "application only",
    "extended_include_high_missing": "joined / include >=50% missing",
    "extended_exclude_high_missing": "joined / drop >=50% missing",
}


def _plot_tradeoff(metrics: pd.DataFrame, destination: Path) -> None:
    """Plot discrimination against mean input PSI for each feature policy."""

    figure, axis = plt.subplots(figsize=FIGURE_SIZE)
    colors = ["#64748b", "#dc2626", "#2563eb"]
    offsets = [(6, 5), (-8, -13), (-8, 6)]
    alignments = ["left", "right", "right"]
    for ((_, row), color, offset, alignment) in zip(
        metrics.iterrows(), colors, offsets, alignments, strict=True
    ):
        axis.scatter(row["mean_psi"], row["roc_auc"], s=95, color=color)
        axis.annotate(
            VARIANT_LABELS[str(row["variant"])],
            (row["mean_psi"], row["roc_auc"]),
            xytext=offset,
            textcoords="offset points",
            ha=alignment,
            fontsize=8,
        )
    axis.set_xlabel("Mean feature PSI (lower is more stable)")
    axis.set_ylabel("Proxy-holdout ROC-AUC")
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(figure)


def _plot_missing_ablation(metrics: pd.DataFrame, destination: Path) -> None:
    """Compare joined models with high-missing aggregate features included or removed."""

    joined = metrics.loc[metrics["variant"].str.startswith("extended")].copy()
    labels = ["include", "exclude"]
    figure, axes = plt.subplots(1, 2, figsize=(9.0, 4.4))
    axes[0].bar(labels, joined["roc_auc"], color=["#dc2626", "#2563eb"])
    axes[0].set_title("Discrimination")
    axes[0].set_ylabel("ROC-AUC")
    axes[0].set_ylim(
        float(joined["roc_auc"].min()) - 0.001,
        float(joined["roc_auc"].max()) + 0.001,
    )
    axes[1].bar(labels, joined["mean_psi"], color=["#dc2626", "#2563eb"])
    axes[1].set_title("Input stability")
    axes[1].set_ylabel("Mean PSI")
    figure.suptitle("Aggregate features with >=50% reference missingness")
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI)
    plt.close(figure)


def _plot_top_psi(psi: pd.DataFrame, destination: Path) -> None:
    """Plot the ten most shifted features for baseline and full joined inputs."""

    variants = ["baseline_application", "extended_include_high_missing"]
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 5.6))
    for axis, variant in zip(axes, variants, strict=True):
        subset = psi.loc[psi["variant"].eq(variant)].nlargest(10, "psi").sort_values("psi")
        axis.barh(subset["feature"], subset["psi"], color="#2563eb")
        axis.set_xlim(0, float(subset["psi"].max()) * 1.18)
        axis.ticklabel_format(axis="x", style="sci", scilimits=(-3, -3))
        axis.text(
            0.98,
            0.02,
            "alert threshold 0.25\n(outside displayed scale)",
            color="#dc2626",
            fontsize=7,
            ha="right",
            va="bottom",
            transform=axis.transAxes,
        )
        axis.set_title(VARIANT_LABELS[variant])
        axis.set_xlabel("PSI")
        axis.tick_params(axis="y", labelsize=7)
    figure.tight_layout()
    figure.savefig(destination, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(figure)


def _variant_psi_rows(
    master: pd.DataFrame,
    variants: dict[str, list[str]],
) -> pd.DataFrame:
    """Create explicit per-variant PSI evidence from one feature calculation."""

    rows = []
    for variant, features in variants.items():
        table = master.loc[master["feature"].isin(features)].copy()
        table.insert(0, "variant", variant)
        table["rank"] = table["psi"].rank(method="first", ascending=False).astype(int)
        rows.append(table)
    return pd.concat(rows, ignore_index=True)


def run_experiment(config: ExperimentConfig) -> dict[str, object]:
    """Run every Ship Gate comparison and persist measured evidence."""

    config.results_dir.mkdir(parents=True, exist_ok=True)
    print("loading application_train", flush=True)
    application = load_application(config.data_dir / "application_train.csv")
    print("aggregating bureau", flush=True)
    bureau = aggregate_bureau(config.data_dir / "bureau.csv")
    print("aggregating previous_application", flush=True)
    previous = aggregate_previous(config.data_dir / "previous_application.csv")
    joined = join_related_tables(application, bureau, previous)
    del bureau, previous
    gc.collect()

    split = make_proxy_order_split(joined, config.id_column, config.train_fraction)
    base_features = [
        column
        for column in application.columns
        if column not in {config.id_column, config.target_column}
    ]
    aggregate_features = [
        column
        for column in joined.columns
        if column.startswith("BUREAU_") or column.startswith("PREV_")
    ]
    all_features = [*base_features, *aggregate_features]
    reference_missing = joined.iloc[split.reference][aggregate_features].isna().mean()
    high_missing = sorted(
        reference_missing.loc[reference_missing >= config.missing_threshold].index.tolist()
    )
    reduced_features = [feature for feature in all_features if feature not in high_missing]
    variants = {
        "baseline_application": base_features,
        "extended_include_high_missing": all_features,
        "extended_exclude_high_missing": reduced_features,
    }

    print(
        f"encoding {len(all_features)} features; high-missing aggregates={len(high_missing)}",
        flush=True,
    )
    x_reference, x_comparison, categorical = encode_train_comparison(
        joined, split, all_features
    )
    y_reference = joined.iloc[split.reference][config.target_column]
    y_comparison = joined.iloc[split.comparison][config.target_column]

    metric_rows: list[dict[str, object]] = []
    importance_rows: list[pd.DataFrame] = []
    fitted_metrics: dict[str, dict[str, float]] = {}
    for variant, features in variants.items():
        print(f"fitting {variant} features={len(features)}", flush=True)
        model = fit_model(x_reference[features], y_reference, config)
        model_metrics = evaluate_model(model, x_comparison[features], y_comparison)
        fitted_metrics[variant] = model_metrics
        metric_rows.append(
            {
                "variant": variant,
                "features": len(features),
                "aggregate_features": sum(
                    feature.startswith(("BUREAU_", "PREV_")) for feature in features
                ),
                "removed_high_missing_aggregates": (
                    len(high_missing) if variant.endswith("exclude_high_missing") else 0
                ),
                "reference_rows": len(split.reference),
                "comparison_rows": len(split.comparison),
                **model_metrics,
            }
        )
        importance_rows.append(feature_importance_table(model, features, variant))
        del model
        gc.collect()

    print("calculating feature-level PSI", flush=True)
    master_psi = feature_psi_table(
        joined,
        split.reference,
        split.comparison,
        all_features,
        bins=config.psi_bins,
    )
    psi = _variant_psi_rows(master_psi, variants)
    metrics = pd.DataFrame(metric_rows)
    psi_summary_rows = []
    for variant in variants:
        summary = summarize_psi(
            psi.loc[psi["variant"].eq(variant)], config.psi_alert_threshold
        )
        psi_summary_rows.append({"variant": variant, **summary})
        for key, value in summary.items():
            metrics.loc[metrics["variant"].eq(variant), key] = value
    psi_summary = pd.DataFrame(psi_summary_rows)

    high_missing_table = master_psi.loc[master_psi["feature"].isin(high_missing)].copy()
    high_missing_table.insert(
        3,
        "reference_missing_threshold",
        config.missing_threshold,
    )
    top_psi = psi.loc[psi["rank"] <= 10].sort_values(["variant", "rank"])
    importance = pd.concat(importance_rows, ignore_index=True)

    baseline = metrics.set_index("variant").loc["baseline_application"]
    include = metrics.set_index("variant").loc["extended_include_high_missing"]
    exclude = metrics.set_index("variant").loc["extended_exclude_high_missing"]
    tradeoff = {
        "split": {
            "proxy": "ascending SK_ID_CURR order",
            "reference_rows": int(len(split.reference)),
            "comparison_rows": int(len(split.comparison)),
            "is_true_temporal_validation": False,
        },
        "data": {
            "application_rows": int(len(application)),
            "target_rate": float(application[config.target_column].mean()),
            "application_features": len(base_features),
            "aggregate_features": len(aggregate_features),
            "high_missing_aggregate_features": len(high_missing),
            "categorical_features": len(categorical),
        },
        "baseline_to_joined": {
            "roc_auc_change": float(include["roc_auc"] - baseline["roc_auc"]),
            "pr_auc_change": float(include["pr_auc"] - baseline["pr_auc"]),
            "mean_psi_change": float(include["mean_psi"] - baseline["mean_psi"]),
            "p95_psi_change": float(include["p95_psi"] - baseline["p95_psi"]),
        },
        "high_missing_ablation": {
            "roc_auc_exclude_minus_include": float(exclude["roc_auc"] - include["roc_auc"]),
            "pr_auc_exclude_minus_include": float(exclude["pr_auc"] - include["pr_auc"]),
            "mean_psi_exclude_minus_include": float(exclude["mean_psi"] - include["mean_psi"]),
            "p95_psi_exclude_minus_include": float(exclude["p95_psi"] - include["p95_psi"]),
        },
        "measurement_boundary": (
            "No application timestamp is available. The ID-ordered cohort is a proxy "
            "distribution-stress test, not evidence of production-time degradation."
        ),
    }

    metrics.to_csv(config.results_dir / "model_metrics.csv", index=False)
    psi.to_csv(config.results_dir / "feature_psi.csv", index=False)
    psi_summary.to_csv(config.results_dir / "psi_summary.csv", index=False)
    top_psi.to_csv(config.results_dir / "top_10_psi.csv", index=False)
    high_missing_table.to_csv(
        config.results_dir / "high_missing_aggregate_features.csv", index=False
    )
    importance.to_csv(config.results_dir / "feature_importance.csv", index=False)
    with (config.results_dir / "tradeoff_summary.json").open("w", encoding="utf-8") as stream:
        json.dump(tradeoff, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    _plot_tradeoff(metrics, config.results_dir / "auc_psi_tradeoff.png")
    _plot_missing_ablation(metrics, config.results_dir / "missing_ablation.png")
    _plot_top_psi(psi, config.results_dir / "top_10_psi.png")
    return tradeoff

