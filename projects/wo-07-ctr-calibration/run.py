"""Run the fixed temporal CTR calibration experiment."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.bidding import bidding_proxy
from src.calibration import PREFERRED_METHOD, fit_calibrators
from src.data import LABEL_COLUMN, ROWS_PER_DAY, load_split
from src.features import MAX_CATEGORIES_PER_FEATURE, MIN_CATEGORY_COUNT, TrainOnlyFeatures
from src.metrics import CURVE_BINS, ECE_BINS, calibration_bins, equal_count_curve, evaluate
from src.models import fit_baseline
from src.report import MODEL_NAMES, write_results


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
RESULTS_DIR = PROJECT_DIR / "results"


def split_summary(frame: object, days: list[str]) -> dict[str, object]:
    """Return row and click counts for one dated partition."""
    return {
        "days": days,
        "rows": int(len(frame)),
        "positive": int(frame[LABEL_COLUMN].sum()),
    }


def main() -> None:
    """Fit the baseline and calibrators, then measure one untouched test set."""
    split = load_split(DATA_DIR)
    features = TrainOnlyFeatures().fit(split.train)
    train_x = features.transform(split.train)
    calibration_x = features.transform(split.calibration)
    test_x = features.transform(split.test)
    model = fit_baseline(train_x, split.train[LABEL_COLUMN].to_numpy())
    calibration_base = np.asarray(model.predict_proba(calibration_x)[:, 1], dtype=float)
    calibrators = fit_calibrators(
        calibration_base, split.calibration[LABEL_COLUMN].to_numpy()
    )
    test_base = np.asarray(model.predict_proba(test_x)[:, 1], dtype=float)
    predictions = calibrators.predict(test_base)
    truth = split.test[LABEL_COLUMN].to_numpy()
    result = {
        "dataset": "criteo/CriteoClickLogs",
        "sample_design": "first 40000 rows of one fixed Parquet shard per day",
        "rows_per_day": ROWS_PER_DAY,
        "preferred_method": PREFERRED_METHOD,
        "preferred_method_basis": "predeclared lower-complexity monotone parametric mapping; test is for comparison only",
        "split": {
            "train": split_summary(split.train, list(split.train_days)),
            "calibration": split_summary(split.calibration, [split.calibration_day]),
            "test": split_summary(split.test, [split.test_day]),
        },
        "feature_rules": {
            "min_category_count": MIN_CATEGORY_COUNT,
            "max_categories_per_feature": MAX_CATEGORIES_PER_FEATURE,
            "fitted_on": "train only",
        },
        "ece_definition": {
            "bins": ECE_BINS,
            "scheme": "equal-width",
            "intervals": "[left,right), except p=1 in final bin",
            "empty_bin": "zero contribution",
            "weight": "bin count / test row count",
        },
        "metrics": {name: evaluate(truth, predictions[name]) for name in MODEL_NAMES},
        "calibration_bins": {
            name: calibration_bins(truth, predictions[name]) for name in MODEL_NAMES
        },
        "plot_curve": {
            "scheme": "equal-count",
            "bins": CURVE_BINS,
            "models": {
                name: equal_count_curve(truth, predictions[name]) for name in MODEL_NAMES
            },
        },
        "bidding_proxy": {
            name: bidding_proxy(truth, predictions[name]) for name in MODEL_NAMES
        },
    }
    write_results(result, RESULTS_DIR)
    for name in MODEL_NAMES:
        print(name, result["metrics"][name], result["bidding_proxy"][name])


if __name__ == "__main__":
    main()
