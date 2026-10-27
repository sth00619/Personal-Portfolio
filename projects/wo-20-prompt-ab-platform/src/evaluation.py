"""Paired SQuAD scoring, bootstrap intervals, and sample-size simulations."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import ttest_1samp, ttest_rel

from .dataset import QAExample
from .scoring import score_answer


BOOTSTRAP_REPETITIONS = 2_000
POWER_REPETITIONS = 2_000
BOOTSTRAP_SEED = 20_071
POWER_SEED = 20_072
ALPHA = 0.05
SAMPLE_SIZES = (10, 30, 50, 100, 200, 300, 500, 1_000)
BOOTSTRAP_BATCH_SIZE = 64


def wilson_interval(successes: int, trials: int) -> list[float]:
    """Return the two-sided 95% Wilson interval for a rate estimate."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Invalid binomial counts")
    z = 1.959963984540054
    rate = successes / trials
    denominator = 1 + z**2 / trials
    center = (rate + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt(rate * (1 - rate) / trials + z**2 / (4 * trials**2)) / denominator
    return [float(max(0, center - margin)), float(min(1, center + margin))]


def holm_adjusted_p_values(p_values: list[float]) -> list[float]:
    """Adjust a family of p-values with Holm's step-down procedure."""
    if not p_values or any(not 0 <= value <= 1 for value in p_values):
        raise ValueError("p-values must be a non-empty list in [0, 1]")
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    running_max = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (len(p_values) - rank) * p_values[int(index)])
        running_max = max(running_max, candidate)
        adjusted[int(index)] = running_max
    return [float(value) for value in adjusted]


def paired_bootstrap_interval(
    differences: np.ndarray,
    repetitions: int = BOOTSTRAP_REPETITIONS,
    seed: int = BOOTSTRAP_SEED,
) -> list[float]:
    """Estimate a two-sided percentile interval for paired mean-score change."""
    if differences.ndim != 1 or len(differences) < 2 or repetitions < 100:
        raise ValueError("Invalid paired bootstrap dimensions")
    rng = np.random.default_rng(seed)
    means = np.empty(repetitions, dtype=float)
    for start in range(0, repetitions, BOOTSTRAP_BATCH_SIZE):
        stop = min(repetitions, start + BOOTSTRAP_BATCH_SIZE)
        indices = rng.integers(0, len(differences), size=(stop - start, len(differences)))
        means[start:stop] = differences[indices].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def paired_metric_summary(
    examples: list[QAExample],
    predictions: dict[str, dict[str, str]],
    segment: str = "all",
    repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, Any]:
    """Compute paired exact match, F1, abstention rates, tests, and intervals."""
    if segment == "answerable":
        selected = [example for example in examples if not example.is_impossible]
    elif segment == "unanswerable":
        selected = [example for example in examples if example.is_impossible]
    elif segment == "all":
        selected = examples
    else:
        raise ValueError(f"Unknown segment: {segment}")
    if not selected:
        raise ValueError(f"Segment {segment} has no examples")
    per_version: dict[str, dict[str, np.ndarray]] = {}
    for version in ("A", "B"):
        if version not in predictions:
            raise ValueError(f"Missing predictions for prompt {version}")
        item_scores = [
            score_answer(
                predictions[version][example.question_id],
                example.answers,
                example.is_impossible,
            )
            for example in selected
        ]
        per_version[version] = {
            "em": np.asarray([float(score["em"]) for score in item_scores]),
            "f1": np.asarray([float(score["f1"]) for score in item_scores]),
            "abstained": np.asarray([bool(score["abstained"]) for score in item_scores]),
        }
    result: dict[str, Any] = {"segment": segment, "n": len(selected)}
    for metric in ("em", "f1"):
        score_a = per_version["A"][metric]
        score_b = per_version["B"][metric]
        differences = score_b - score_a
        test = ttest_rel(score_b, score_a, alternative="two-sided")
        p_value = float(test.pvalue) if np.isfinite(test.pvalue) else 1.0
        result[metric] = {
            "mean_a": float(score_a.mean()),
            "mean_b": float(score_b.mean()),
            "difference_b_minus_a": float(differences.mean()),
            "difference_percentage_points": float(100 * differences.mean()),
            "paired_t_p_value_two_sided": p_value,
            "paired_bootstrap_95_ci": paired_bootstrap_interval(
                differences, repetitions=repetitions,
                seed=BOOTSTRAP_SEED + (0 if metric == "em" else 1) + len(selected),
            ),
        }
    if segment == "unanswerable":
        for version in ("A", "B"):
            result[f"{version.lower()}_abstention_rate"] = float(
                per_version[version]["abstained"].mean()
            )
    elif segment == "answerable":
        for version in ("A", "B"):
            result[f"{version.lower()}_false_abstention_rate"] = float(
                per_version[version]["abstained"].mean()
            )
    return result


def estimate_sample_size_power(
    differences: np.ndarray,
    repetitions: int = POWER_REPETITIONS,
    sizes: tuple[int, ...] = SAMPLE_SIZES,
    seed: int = POWER_SEED,
) -> list[dict[str, Any]]:
    """Estimate two-sided paired t-test power by resampling observed item deltas."""
    if differences.ndim != 1 or len(differences) < 2:
        raise ValueError("Power estimation needs a one-dimensional paired-difference vector")
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for sample_size in sizes:
        draws = rng.choice(differences, size=(repetitions, sample_size), replace=True)
        tests = ttest_1samp(draws, popmean=0, axis=1, alternative="two-sided")
        significant = np.asarray(tests.pvalue < ALPHA, dtype=bool)
        count = int(significant.sum())
        rows.append({
            "sample_size": sample_size,
            "repetitions": repetitions,
            "alpha_two_sided": ALPHA,
            "observed_effect_mean_f1_delta": float(differences.mean()),
            "estimated_power": count / repetitions,
            "estimated_power_95_wilson": wilson_interval(count, repetitions),
        })
    return rows


def small_sample_direction(
    differences: np.ndarray,
    sample_size: int = 10,
    repetitions: int = 2_000,
    seed: int = POWER_SEED + 1,
) -> dict[str, float | int]:
    """Compare repeated small-sample impressions with the full-set F1 direction."""
    if sample_size < 1 or repetitions < 1 or differences.ndim != 1:
        raise ValueError("Invalid small-sample simulation input")
    rng = np.random.default_rng(seed)
    sample_means = rng.choice(
        differences, size=(repetitions, sample_size), replace=True
    ).mean(axis=1)
    full_direction = np.sign(float(differences.mean()))
    if full_direction > 0:
        agreement = sample_means > 0
    elif full_direction < 0:
        agreement = sample_means < 0
    else:
        agreement = sample_means == 0
    return {
        "sample_size": sample_size,
        "repetitions": repetitions,
        "full_set_mean_difference": float(differences.mean()),
        "fraction_matching_full_set_direction": float(agreement.mean()),
        "sample_mean_difference_p05": float(np.quantile(sample_means, 0.05)),
        "sample_mean_difference_median": float(np.median(sample_means)),
        "sample_mean_difference_p95": float(np.quantile(sample_means, 0.95)),
    }


def score_all(
    examples: list[QAExample], predictions: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """Calculate primary and segmented metrics plus corrected segment tests."""
    summaries = {
        segment: paired_metric_summary(examples, predictions, segment)
        for segment in ("all", "answerable", "unanswerable")
    }
    f1_p_values = [
        summaries[segment]["f1"]["paired_t_p_value_two_sided"]
        for segment in ("answerable", "unanswerable")
    ]
    adjusted = holm_adjusted_p_values(f1_p_values)
    for index, segment in enumerate(("answerable", "unanswerable")):
        summaries[segment]["f1"]["holm_adjusted_p_value_two_sided"] = adjusted[index]
    score_a = np.asarray([
        score_answer(
            predictions["A"][example.question_id], example.answers, example.is_impossible
        )["f1"]
        for example in examples
    ], dtype=float)
    score_b = np.asarray([
        score_answer(
            predictions["B"][example.question_id], example.answers, example.is_impossible
        )["f1"]
        for example in examples
    ], dtype=float)
    differences = score_b - score_a
    return {
        "metrics": summaries,
        "sample_size_power": estimate_sample_size_power(differences),
        "small_sample_impression": small_sample_direction(differences),
    }
