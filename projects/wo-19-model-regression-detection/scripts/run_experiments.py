"""Train the WO-07 baseline and benchmark segment regression detectors."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import ttest_1samp


ROOT = Path(__file__).resolve().parents[1]
WO07_ROOT = ROOT.parent / "wo-07-ctr-calibration"
if str(WO07_ROOT) not in sys.path:
    sys.path.insert(0, str(WO07_ROOT))

from data.prepare_avazu import SAMPLE  # noqa: E402
from src.avazu import (  # noqa: E402
    LABEL,
    MODEL_LEARNING_RATE,
    MODEL_LEAVES,
    MODEL_MIN_CHILD,
    MODEL_SEED,
    MODEL_TREES,
    TEST_DAYS,
    AvazuFeatures,
    chronological_split,
    fit_avazu_baseline,
    load_sample,
)
from regression import (  # noqa: E402
    holm_rejections,
    inject_neutral_version,
    inject_regression,
    paired_bootstrap_upper_bounds,
)


OUTPUT = ROOT / "results"
SEGMENT_COLUMN = "device_type"
MINIMUM_SEGMENT_ROWS = 1_000
TARGET_SEGMENT = "0"
MIN_REGRESSION_POINTS = 0.05
REGRESSION_POINTS = 0.10
NEUTRAL_SWAP_FRACTION = 0.05
SAMPLE_SIZES = (50, 200, 1_000)
MONTE_CARLO_REPETITIONS = 2_000
BOOTSTRAP_REPETITIONS = 1_000
ALPHA = 0.05
RANDOM_SEED = 19_071


def wilson_interval(successes: int, trials: int, z_value: float = 1.96) -> list[float]:
    """Calculate a two-sided Wilson interval for a measured simulation rate."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Invalid binomial counts")
    proportion = successes / trials
    denominator = 1 + z_value**2 / trials
    center = (proportion + z_value**2 / (2 * trials)) / denominator
    margin = z_value * np.sqrt(
        proportion * (1 - proportion) / trials + z_value**2 / (4 * trials**2)
    ) / denominator
    return [float(max(0, center - margin)), float(min(1, center + margin))]


def accuracy(correct: np.ndarray) -> float:
    """Return binary accuracy as the mean of correctness indicators."""
    return float(np.mean(correct))


def paired_t_p_values(differences: np.ndarray) -> np.ndarray:
    """Compute one-sided paired t-test p-values, treating zero variance as null."""
    result = ttest_1samp(differences, popmean=0, alternative="less", axis=1)
    return np.nan_to_num(np.asarray(result.pvalue), nan=1.0, posinf=1.0, neginf=0.0)


def dataset_fingerprint(path: Path) -> str:
    """Hash the exact compressed golden sample used for training and evaluation."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_baseline() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Reuse the WO-07 temporal split, feature builder, and LightGBM baseline."""
    if not SAMPLE.is_file():
        raise FileNotFoundError(
            f"Missing {SAMPLE}; prepare the audited sample using WO-07 first"
        )
    frame = load_sample(SAMPLE)
    split = chronological_split(frame)
    if tuple(sorted(split.test["day"].unique())) != TEST_DAYS:
        raise ValueError("WO-07 final two-day evaluation partition changed")
    feature_builder = AvazuFeatures().fit(split.train)
    train_features = feature_builder.transform(split.train)
    test_features = feature_builder.transform(split.test)
    train_labels = split.train[LABEL].to_numpy(dtype=np.int8)
    labels = split.test[LABEL].to_numpy(dtype=np.int8)
    segment_values = split.test[SEGMENT_COLUMN].astype(str).to_numpy()
    model = fit_avazu_baseline(train_features, train_labels)
    probabilities = np.asarray(model.predict_proba(test_features)[:, 1], dtype=float)
    baseline_correct = (probabilities >= 0.5) == labels.astype(bool)
    counts = {
        str(segment): int(np.sum(segment_values == segment))
        for segment in sorted(set(segment_values))
    }
    eligible = tuple(
        segment for segment, count in counts.items() if count >= MINIMUM_SEGMENT_ROWS
    )
    if TARGET_SEGMENT not in eligible:
        raise ValueError("Predeclared target segment does not meet the support threshold")
    metadata = {
        "source_project": "WO-07 Avazu independent temporal evaluation",
        "sample_file": "projects/wo-07-ctr-calibration/data/avazu_sample.csv.gz",
        "sample_sha256": dataset_fingerprint(SAMPLE),
        "split_days": list(TEST_DAYS),
        "test_rows": int(len(labels)),
        "test_clicks": int(labels.sum()),
        "test_click_rate": float(labels.mean()),
        "segment_column": SEGMENT_COLUMN,
        "segment_counts": counts,
        "minimum_segment_rows": MINIMUM_SEGMENT_ROWS,
        "eligible_segments": list(eligible),
        "excluded_segments": {
            segment: count for segment, count in counts.items()
            if segment not in eligible
        },
        "base_model": {
            "implementation": "WO-07 src/avazu.py fit_avazu_baseline",
            "trees": MODEL_TREES,
            "leaves": MODEL_LEAVES,
            "min_child_samples": MODEL_MIN_CHILD,
            "learning_rate": MODEL_LEARNING_RATE,
            "random_state": MODEL_SEED,
            "decision_threshold": 0.5,
        },
    }
    return baseline_correct.astype(bool), segment_values, labels, metadata


def summarize_versions(
    baseline: np.ndarray,
    no_regression: np.ndarray,
    regression: np.ndarray,
    segments: np.ndarray,
    eligible_segments: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Report global and per-segment accuracy for all synthetic versions."""
    rows: list[dict[str, Any]] = []
    for segment in ("ALL", *eligible_segments):
        mask = np.ones(len(segments), dtype=bool) if segment == "ALL" else segments == segment
        rows.append({
            "segment": segment,
            "rows": int(mask.sum()),
            "baseline_accuracy": accuracy(baseline[mask]),
            "no_regression_accuracy": accuracy(no_regression[mask]),
            "injected_regression_accuracy": accuracy(regression[mask]),
            "regression_drop_percentage_points": 100 * (
                accuracy(baseline[mask]) - accuracy(regression[mask])
            ),
        })
    return rows


def simulate_sample_sizes(
    baseline: np.ndarray,
    no_regression: np.ndarray,
    regression: np.ndarray,
    segments: np.ndarray,
    eligible_segments: tuple[str, ...],
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Estimate family-wise false-positive rates and target-segment power."""
    group_indices = {
        segment: np.flatnonzero(segments == segment) for segment in eligible_segments
    }
    output: list[dict[str, Any]] = []
    for sample_size in SAMPLE_SIZES:
        if any(len(indices) < sample_size for indices in group_indices.values()):
            raise ValueError(f"A segment cannot supply {sample_size} evaluation rows")
        null_differences: list[np.ndarray] = []
        regression_differences: list[np.ndarray] = []
        for segment in eligible_segments:
            indices = rng.choice(
                group_indices[segment],
                size=(MONTE_CARLO_REPETITIONS, sample_size),
                replace=True,
            )
            sampled_baseline = baseline[indices]
            null_differences.append(
                no_regression[indices].astype(np.int8) - sampled_baseline.astype(np.int8)
            )
            regression_differences.append(
                regression[indices].astype(np.int8) - sampled_baseline.astype(np.int8)
            )
        null_matrix = np.stack(null_differences, axis=2)
        regression_matrix = np.stack(regression_differences, axis=2)
        null_p_values = np.stack(
            [paired_t_p_values(null_matrix[:, :, index]) for index in range(len(eligible_segments))],
            axis=1,
        )
        regression_p_values = np.stack(
            [paired_t_p_values(regression_matrix[:, :, index]) for index in range(len(eligible_segments))],
            axis=1,
        )
        null_t_rejections = holm_rejections(null_p_values, ALPHA)
        regression_t_rejections = holm_rejections(regression_p_values, ALPHA)
        null_practical_rejections = null_t_rejections & (np.mean(null_matrix, axis=1) <= -MIN_REGRESSION_POINTS)
        regression_practical_rejections = regression_t_rejections & (
            np.mean(regression_matrix, axis=1) <= -MIN_REGRESSION_POINTS
        )

        family_confidence = 1 - ALPHA / len(eligible_segments)
        null_boot_rejections = np.zeros_like(null_t_rejections)
        regression_boot_rejections = np.zeros_like(regression_t_rejections)
        for index in range(len(eligible_segments)):
            null_upper = paired_bootstrap_upper_bounds(
                null_matrix[:, :, index], family_confidence, BOOTSTRAP_REPETITIONS, rng
            )
            regression_upper = paired_bootstrap_upper_bounds(
                regression_matrix[:, :, index], family_confidence, BOOTSTRAP_REPETITIONS, rng
            )
            null_boot_rejections[:, index] = null_upper < 0
            regression_boot_rejections[:, index] = regression_upper < 0
        null_boot_practical = null_boot_rejections & (
            np.mean(null_matrix, axis=1) <= -MIN_REGRESSION_POINTS
        )
        regression_boot_practical = regression_boot_rejections & (
            np.mean(regression_matrix, axis=1) <= -MIN_REGRESSION_POINTS
        )

        target_index = eligible_segments.index(TARGET_SEGMENT)
        for name, null_flags, power_flags, null_operational, power_operational in (
            (
                "paired_t_holm", null_t_rejections, regression_t_rejections,
                null_practical_rejections, regression_practical_rejections,
            ),
            (
                "paired_bootstrap_bonferroni", null_boot_rejections, regression_boot_rejections,
                null_boot_practical, regression_boot_practical,
            ),
        ):
            statistical_false_positives = int(np.sum(np.any(null_flags, axis=1)))
            operational_false_positives = int(np.sum(np.any(null_operational, axis=1)))
            statistical_detections = int(np.sum(power_flags[:, target_index]))
            operational_detections = int(np.sum(power_operational[:, target_index]))
            output.append({
                "sample_size_per_segment": sample_size,
                "monte_carlo_repetitions": MONTE_CARLO_REPETITIONS,
                "method": name,
                "family_false_positive_rate": operational_false_positives / MONTE_CARLO_REPETITIONS,
                "family_false_positive_rate_95_wilson": wilson_interval(
                    operational_false_positives, MONTE_CARLO_REPETITIONS
                ),
                "family_significance_only_false_positive_rate": statistical_false_positives / MONTE_CARLO_REPETITIONS,
                "family_significance_only_false_positive_rate_95_wilson": wilson_interval(
                    statistical_false_positives, MONTE_CARLO_REPETITIONS
                ),
                "target_detection_power": operational_detections / MONTE_CARLO_REPETITIONS,
                "target_detection_power_95_wilson": wilson_interval(
                    operational_detections, MONTE_CARLO_REPETITIONS
                ),
                "target_significance_only_power": statistical_detections / MONTE_CARLO_REPETITIONS,
                "target_significance_only_power_95_wilson": wilson_interval(
                    statistical_detections, MONTE_CARLO_REPETITIONS
                ),
                "target_segment": TARGET_SEGMENT,
                "segments_in_family": list(eligible_segments),
                "family_alpha": ALPHA,
                "bootstrap_repetitions": (
                    BOOTSTRAP_REPETITIONS if name == "paired_bootstrap_bonferroni" else None
                ),
            })
    return output


def paired_full_test(
    baseline: np.ndarray,
    no_regression: np.ndarray,
    regression: np.ndarray,
    segments: np.ndarray,
    eligible_segments: tuple[str, ...],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Report target effect, raw t-test p-value, and paired bootstrap interval."""
    rows: dict[str, Any] = {}
    family_confidence = 1 - ALPHA / len(eligible_segments)
    for version_name, version in (
        ("no_regression", no_regression),
        ("injected_regression", regression),
    ):
        p_values: list[float] = []
        for segment in eligible_segments:
            differences = (
                version[segments == segment].astype(np.int8)
                - baseline[segments == segment].astype(np.int8)
            )
            p = float(ttest_1samp(differences, popmean=0, alternative="less").pvalue)
            p_values.append(1.0 if np.isnan(p) else p)
        target = segments == TARGET_SEGMENT
        target_diff = (
            version[target].astype(np.int8) - baseline[target].astype(np.int8)
        )
        n = len(target_diff)
        bootstrap = rng.binomial(
            n,
            np.mean(target_diff == -1),
            size=BOOTSTRAP_REPETITIONS,
        )
        positive_probability = (
            np.mean(target_diff == 1)
            / max(1e-15, 1 - np.mean(target_diff == -1))
        )
        positive = rng.binomial(n - bootstrap, positive_probability)
        means = (positive - bootstrap) / n
        rows[version_name] = {
            "target_segment": TARGET_SEGMENT,
            "target_rows": n,
            "accuracy_difference": float(np.mean(target_diff)),
            "accuracy_difference_percentage_points": float(100 * np.mean(target_diff)),
            "paired_t_test_one_sided_p": p_values[eligible_segments.index(TARGET_SEGMENT)],
            "holm_adjusted_p": float(
                min(1.0, p_values[eligible_segments.index(TARGET_SEGMENT)] * len(eligible_segments))
            ),
            "paired_bootstrap_95_percentile_interval": [
                float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))
            ],
            "paired_bootstrap_family_adjusted_upper_bound": float(
                np.quantile(means, family_confidence)
            ),
            "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
            "segment_raw_p_values": dict(zip(eligible_segments, p_values, strict=True)),
        }
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of flat measurement records as UTF-8 CSV."""
    if not rows:
        raise ValueError("Cannot write an empty measurement table")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def main() -> None:
    """Build A/B/C versions, run detectors, and persist aggregate evidence."""
    rng = np.random.default_rng(RANDOM_SEED)
    baseline, segments, labels, metadata = load_baseline()
    eligible = tuple(metadata["eligible_segments"])
    no_regression = inject_neutral_version(
        baseline, segments, eligible, NEUTRAL_SWAP_FRACTION, rng
    )
    regression = inject_regression(
        baseline, segments, TARGET_SEGMENT, eligible, REGRESSION_POINTS, rng
    )
    version_rows = summarize_versions(baseline, no_regression, regression, segments, eligible)
    sample_rows = simulate_sample_sizes(
        baseline, no_regression, regression, segments, eligible, rng
    )
    full_test = paired_full_test(
        baseline, no_regression, regression, segments, eligible, rng
    )
    global_rows = version_rows[0]
    if not (
        global_rows["baseline_accuracy"]
        == global_rows["no_regression_accuracy"]
        == global_rows["injected_regression_accuracy"]
    ):
        raise AssertionError("A/B/C global accuracy must match by construction")
    metadata.update({
        "golden_set_methodology": (
            "Reuse WO-07's audited Avazu temporal holdout; regression detector claims are "
            "benchmarked by label-guided synthetic correctness mutations"
        ),
        "target_definition": {
            "segment": {SEGMENT_COLUMN: TARGET_SEGMENT},
            "metric": "binary accuracy at probability threshold 0.5",
            "regression": f"at least {100 * MIN_REGRESSION_POINTS:.1f} percentage-point observed decrease plus adjusted p < {ALPHA}",
            "minimum_effect_for_flag": f"observed accuracy decrease >= {100 * MIN_REGRESSION_POINTS:.1f} percentage points",
            "alternative": "one-sided paired test of model-version correctness differences < 0",
            "alpha": ALPHA,
            "multiple_testing": "Holm step-down for paired t-tests; Bonferroni family-wise upper bootstrap bound",
        },
        "synthetic_versions": {
            "A": "WO-07 LightGBM raw-probability baseline thresholded at 0.5",
            "B": "Flip target-segment correct decisions to wrong; offset equal count of errors in control segments to preserve global accuracy",
            "C": "Swap equal correct/error decisions inside each eligible segment to preserve each segment's accuracy",
            "label_guided_injection": True,
            "limitation": "Mutations use held-out labels and validate detector behavior, not realistic retraining or deployable model versions",
            "random_seed": RANDOM_SEED,
            "regression_points": REGRESSION_POINTS,
            "minimum_detectable_effect_points": MIN_REGRESSION_POINTS,
            "neutral_swap_fraction": NEUTRAL_SWAP_FRACTION,
        },
        "simulation": {
            "sample_sizes_per_segment": list(SAMPLE_SIZES),
            "monte_carlo_repetitions": MONTE_CARLO_REPETITIONS,
            "bootstrap_repetitions_per_simulated_sample": BOOTSTRAP_REPETITIONS,
            "sampling": "independent with-replacement draws from the fixed WO-07 holdout segment rows",
            "false_positive_definition": "at least one eligible segment is flagged under version C using both the adjusted significance and minimum-effect rules",
            "significance_only_false_positive_definition": "at least one eligible segment passes the adjusted significance rule under version C, without the minimum-effect rule",
            "power_definition": f"target segment {TARGET_SEGMENT} passes both rules under version B",
        },
    })
    result = {
        "dataset": metadata,
        "versions": version_rows,
        "full_holdout_paired_tests": full_test,
        "sample_size_simulation": sample_rows,
        "measurement_boundary": [
            "The 0.5 threshold turns a CTR probability model into a deliberately narrow accuracy-only detector benchmark.",
            "The synthetic C and B variants use the held-out labels; measured power and false-positive rates are conditional on this injection design.",
            "A fixed sampled holdout and repeated resampling do not estimate performance across future traffic distributions or retraining seeds.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "experiment_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    write_csv(OUTPUT / "version_metrics.csv", version_rows)
    write_csv(OUTPUT / "sample_size_rates.csv", sample_rows)
    print(json.dumps({
        "global_versions": version_rows[0],
        "target_segment": version_rows[1],
        "full_holdout_tests": full_test,
        "sample_size_rates": sample_rows,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
