"""Evaluate CTR calibration on a disjoint Avazu temporal experiment."""

from __future__ import annotations

import csv
import gc
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data.prepare_avazu import SAMPLE, prepare_avazu
from src.avazu import (
    BOOTSTRAP_REPEATS, CALIBRATION_DAYS, LABEL, MAX_CATEGORIES_PER_FEATURE,
    MIN_CATEGORY_COUNT, MODEL_LEAVES, MODEL_LEARNING_RATE,
    MODEL_MIN_CHILD, MODEL_TREES, TEST_DAYS, TRAIN_DAYS,
    AvazuFeatures, chronological_split, fit_avazu_baseline, load_sample,
    paired_bootstrap,
)
from src.calibration import PREFERRED_METHOD, fit_calibrators
from src.metrics import CURVE_BINS, ECE_BINS, calibration_bins, equal_count_curve, evaluate
from src.report import MODEL_LABELS, MODEL_NAMES, plot_curve


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "results" / "avazu"


def split_summary(frame: pd.DataFrame) -> dict[str, Any]:
    """Count rows and clicks without disclosing raw competition records."""
    grouped = frame.groupby("day", observed=True)[LABEL].agg(["size", "sum"])
    return {
        "days": [str(day) for day in grouped.index],
        "rows": int(len(frame)),
        "clicks": int(frame[LABEL].sum()),
        "by_day": {
            str(day): {"rows": int(row["size"]), "clicks": int(row["sum"])}
            for day, row in grouped.iterrows()
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write measured metric rows with stable columns."""
    if not rows:
        raise ValueError("Metric table cannot be empty")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Audit the archive, fit only earlier days, and save held-out results."""
    audit = prepare_avazu()
    frame = load_sample(SAMPLE)
    if len(frame) != audit["sample_rows"]:
        raise ValueError("Sample row count differs from source audit")
    split = chronological_split(frame)
    summaries = {
        "train": split_summary(split.train),
        "calibration": split_summary(split.calibration),
        "test": split_summary(split.test),
    }
    if (
        tuple(summaries["train"]["days"]) != TRAIN_DAYS
        or tuple(summaries["calibration"]["days"]) != CALIBRATION_DAYS
        or tuple(summaries["test"]["days"]) != TEST_DAYS
    ):
        raise AssertionError("Temporal split changed")
    print(f"Avazu sample: {audit['sample_rows']}; split: {[item['rows'] for item in summaries.values()]}", flush=True)

    feature_builder = AvazuFeatures().fit(split.train)
    train_features = feature_builder.transform(split.train)
    calibration_features = feature_builder.transform(split.calibration)
    test_features = feature_builder.transform(split.test)
    train_labels = split.train[LABEL].to_numpy(dtype=np.int8)
    calibration_labels = split.calibration[LABEL].to_numpy(dtype=np.int8)
    test_labels = split.test[LABEL].to_numpy(dtype=np.int8)
    test_days = split.test["day"].astype(str).to_numpy()
    del frame, split
    gc.collect()

    model = fit_avazu_baseline(train_features, train_labels)
    del train_features, train_labels
    gc.collect()
    calibration_raw = np.asarray(
        model.predict_proba(calibration_features)[:, 1], dtype=float
    )
    del calibration_features
    calibrators = fit_calibrators(calibration_raw, calibration_labels)
    test_raw = np.asarray(model.predict_proba(test_features)[:, 1], dtype=float)
    del test_features
    predictions = calibrators.predict(test_raw)
    metrics = {name: evaluate(test_labels, predictions[name]) for name in MODEL_NAMES}
    per_day_metrics = {
        str(day): {
            name: evaluate(test_labels[test_days == day], predictions[name][test_days == day])
            for name in MODEL_NAMES
        }
        for day in TEST_DAYS
    }
    paired_improvements = paired_bootstrap(
        test_labels, predictions, test_days, ECE_BINS
    )
    result: dict[str, Any] = {
        "dataset": "Kaggle Avazu CTR Prediction train.gz",
        "source_audit": audit,
        "sample_design": "crc32(id) modulo 40 equals 17; full log stays in hour order",
        "split": summaries,
        "model": {
            "trees": MODEL_TREES,
            "leaves": MODEL_LEAVES,
            "min_child_samples": MODEL_MIN_CHILD,
            "learning_rate": MODEL_LEARNING_RATE,
            "min_category_count": MIN_CATEGORY_COUNT,
            "max_categories_per_feature": MAX_CATEGORIES_PER_FEATURE,
            "feature_vocab_fit": "train only",
            "predeclared_preferred_calibrator": PREFERRED_METHOD,
        },
        "ece_definition": {"bins": ECE_BINS, "scheme": "equal-width"},
        "metrics": metrics,
        "per_day_metrics": per_day_metrics,
        "paired_improvements": {
            "bootstrap_samples": BOOTSTRAP_REPEATS,
            "method": "row bootstrap stratified by held-out day; fitted model held fixed",
            "vs_baseline": paired_improvements,
        },
        "calibration_bins": {
            name: calibration_bins(test_labels, predictions[name]) for name in MODEL_NAMES
        },
        "plot_curve": {
            "scheme": "equal-count",
            "bins": CURVE_BINS,
            "models": {
                name: equal_count_curve(test_labels, predictions[name])
                for name in MODEL_NAMES
            },
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_csv(
        OUTPUT / "metrics.csv",
        [{"model": name, **metrics[name]} for name in MODEL_NAMES],
    )
    write_csv(
        OUTPUT / "per_day_metrics.csv",
        [
            {"day": day, "model": name, **per_day_metrics[day][name]}
            for day in TEST_DAYS for name in MODEL_NAMES
        ],
    )
    plot_curve(result, OUTPUT / "calibration_curve.png")
    for name in MODEL_NAMES:
        print(MODEL_LABELS[name], metrics[name], flush=True)


if __name__ == "__main__":
    main()
