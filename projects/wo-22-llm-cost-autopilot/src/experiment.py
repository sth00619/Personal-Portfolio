"""Run the paired SQuAD cost-routing and semantic-cache replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from data.download import EXPECTED_SHA256
from .cost import HIGH_COST_PROFILE, LOW_COST_PROFILE, PriceProfile, request_cost_usd
from .dataset import Example, load_examples
from .routing import ROUTE_THRESHOLDS, fit_router, group_split, true_easy
from .scoring import answer_f1, is_abstention, normalize_answer
from .semantic_cache import evaluate_replay, fit_semantic_policy


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_DIR / "results"
DEFAULT_ROUTE_THRESHOLD = 0.50
BOOTSTRAP_RESAMPLES = 2_000
SVG_WIDTH = 900
SVG_HEIGHT = 520


def answer_em(prediction: str, references: tuple[str, ...], impossible: bool) -> float:
    """Return normalized exact match, including correct abstentions."""
    normalized = normalize_answer(prediction)
    if impossible:
        return float(is_abstention(prediction))
    return float(any(normalized == normalize_answer(reference) for reference in references))


def model_metrics(examples: list[Example], choices: list[str]) -> dict[str, Any]:
    """Aggregate SQuAD quality and answerability metrics for selected outputs."""
    if len(examples) != len(choices):
        raise ValueError("Every example must have one selected output")
    records: list[dict[str, float | bool]] = []
    for item, choice in zip(examples, choices):
        prediction = item.answer_a if choice == "A" else item.answer_b
        records.append({
            "f1": answer_f1(prediction, item.answers, item.impossible),
            "em": answer_em(prediction, item.answers, item.impossible),
            "abstained": is_abstention(prediction),
        })
    output: dict[str, Any] = {
        "count": len(examples),
        "f1": float(np.mean([float(row["f1"]) for row in records])),
        "exact_match": float(np.mean([float(row["em"]) for row in records])),
        "abstention_rate": float(np.mean([float(row["abstained"]) for row in records])),
        "answerable_f1": float(np.mean([
            float(row["f1"]) for item, row in zip(examples, records) if not item.impossible
        ])),
        "unanswerable_f1": float(np.mean([
            float(row["f1"]) for item, row in zip(examples, records) if item.impossible
        ])),
        "answerable_false_abstention_rate": float(np.mean([
            float(row["abstained"]) for item, row in zip(examples, records) if not item.impossible
        ])),
        "unanswerable_abstention_rate": float(np.mean([
            float(row["abstained"]) for item, row in zip(examples, records) if item.impossible
        ])),
    }
    return output


def _request_cost(item: Example, choice: str, profile: PriceProfile) -> float:
    """Calculate one selected historical response under a price profile."""
    if choice == "A":
        inputs, outputs = item.input_tokens_a, item.output_tokens_a
    else:
        inputs, outputs = item.input_tokens_b, item.output_tokens_b
    return request_cost_usd(inputs, outputs, profile)


def _tier_cost(item: Example, choice: str) -> float:
    """Apply the economy rate to A and the premium rate to B."""
    profile = LOW_COST_PROFILE if choice == "A" else HIGH_COST_PROFILE
    return _request_cost(item, choice, profile)


def _cost_totals(examples: list[Example], choices: list[str]) -> dict[str, float]:
    """Return tiered strategy cost and both uniform-rate sensitivity totals."""
    return {
        "tiered_cost_usd": float(sum(
            _tier_cost(item, choice) for item, choice in zip(examples, choices)
        )),
        "economy_rate_cost_usd": float(sum(
            _request_cost(item, choice, LOW_COST_PROFILE)
            for item, choice in zip(examples, choices)
        )),
        "premium_rate_cost_usd": float(sum(
            _request_cost(item, choice, HIGH_COST_PROFILE)
            for item, choice in zip(examples, choices)
        )),
    }


def _policy_metrics(examples: list[Example], choices: list[str]) -> dict[str, Any]:
    """Return quality, route proportions, and both price-profile totals."""
    output = model_metrics(examples, choices)
    output.update(_cost_totals(examples, choices))
    output["economy_route_rate"] = sum(choice == "A" for choice in choices) / len(choices)
    output["premium_route_rate"] = 1.0 - float(output["economy_route_rate"])
    return output


def _bootstrap_mean(values: np.ndarray) -> list[float]:
    """Return a deterministic percentile interval for a paired mean difference."""
    rng = np.random.default_rng(22_022)
    draws = rng.integers(0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values)))
    means = values[draws].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def _route_error_impact(examples: list[Example], decisions: list[str]) -> dict[str, Any]:
    """Separate hard-to-economy quality loss and easy-to-premium cost regret."""
    hard_to_easy: list[tuple[Example, float]] = []
    easy_to_hard: list[tuple[Example, float]] = []
    for item, choice in zip(examples, decisions):
        actual_easy = true_easy(item)
        delta = (
            answer_f1(item.answer_b, item.answers, item.impossible)
            - answer_f1(item.answer_a, item.answers, item.impossible)
        )
        if not actual_easy and choice == "A":
            hard_to_easy.append((item, delta))
        elif actual_easy and choice == "B":
            easy_to_hard.append((item, delta))
    return {
        "hard_routed_to_economy": {
            "count": len(hard_to_easy),
            "mean_quality_loss_f1_vs_premium": float(np.mean([delta for _, delta in hard_to_easy])) if hard_to_easy else 0.0,
            "quality_loss_sum_f1_points": float(sum(delta for _, delta in hard_to_easy)),
            "tiered_cost_avoided_usd": float(sum(
                _request_cost(item, "B", HIGH_COST_PROFILE)
                - _request_cost(item, "A", LOW_COST_PROFILE)
                for item, _ in hard_to_easy
            )),
        },
        "easy_routed_to_premium": {
            "count": len(easy_to_hard),
            "mean_quality_headroom_f1": float(np.mean([delta for _, delta in easy_to_hard])) if easy_to_hard else 0.0,
            "tiered_extra_cost_usd": float(sum(
                _request_cost(item, "B", HIGH_COST_PROFILE)
                - _request_cost(item, "A", LOW_COST_PROFILE)
                for item, _ in easy_to_hard
            )),
        },
    }


def _tradeoff_curve(
    examples: list[Example], probabilities: np.ndarray, premium_baseline: dict[str, Any]
) -> list[dict[str, float]]:
    """Evaluate predeclared probability cutoffs without tuning on test labels."""
    baseline_cost = float(premium_baseline["tiered_cost_usd"])
    points: list[dict[str, float]] = []
    for threshold in ROUTE_THRESHOLDS:
        choices = ["A" if probability >= threshold else "B" for probability in probabilities]
        metrics = _policy_metrics(examples, choices)
        points.append({
            "threshold": threshold,
            "f1": float(metrics["f1"]),
            "exact_match": float(metrics["exact_match"]),
            "tiered_cost_usd": float(metrics["tiered_cost_usd"]),
            "tiered_savings_percent": 100.0 * (
                1.0 - float(metrics["tiered_cost_usd"]) / baseline_cost
            ) if baseline_cost else 0.0,
            "economy_route_rate": float(metrics["economy_route_rate"]),
        })
    return points


def _write_svg(points: list[dict[str, float]], path: Path) -> None:
    """Write a self-contained SVG cost-quality curve with no plotting runtime."""
    margin_left, margin_right, margin_top, margin_bottom = 90, 36, 54, 90
    plot_w = SVG_WIDTH - margin_left - margin_right
    plot_h = SVG_HEIGHT - margin_top - margin_bottom
    xs = [float(point["tiered_savings_percent"]) for point in points]
    ys = [100.0 * float(point["f1"]) for point in points]
    x_max = max(1.0, max(xs) * 1.08)
    y_min = max(0.0, min(ys) - 5.0)
    y_max = min(100.0, max(ys) + 5.0)
    if y_max <= y_min:
        y_max = y_min + 1.0
    to_x = lambda value: margin_left + (value / x_max) * plot_w
    to_y = lambda value: margin_top + (1.0 - (value - y_min) / (y_max - y_min)) * plot_h
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="450" y="30" text-anchor="middle" font-family="sans-serif" font-size="19" font-weight="bold">WO-22 Cost–Quality Trade-off</text>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#222"/>',
        f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#222"/>',
        f'<text x="{margin_left + plot_w / 2}" y="{SVG_HEIGHT - 28}" text-anchor="middle" font-family="sans-serif" font-size="14">Tiered rate cost savings vs all-premium (%)</text>',
        f'<text x="22" y="{margin_top + plot_h / 2}" transform="rotate(-90 22 {margin_top + plot_h / 2})" text-anchor="middle" font-family="sans-serif" font-size="14">SQuAD token F1 (%)</text>',
    ]
    for tick in range(0, 6):
        x_value = x_max * tick / 5
        x = to_x(x_value)
        elements.extend([
            f'<line x1="{x:.2f}" y1="{margin_top}" x2="{x:.2f}" y2="{margin_top + plot_h}" stroke="#e7eaf0"/>',
            f'<text x="{x:.2f}" y="{margin_top + plot_h + 22}" text-anchor="middle" font-family="sans-serif" font-size="11">{x_value:.0f}</text>',
        ])
    for tick in range(0, 5):
        y_value = y_min + (y_max - y_min) * tick / 4
        y = to_y(y_value)
        elements.extend([
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_w}" y2="{y:.2f}" stroke="#e7eaf0"/>',
            f'<text x="{margin_left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="sans-serif" font-size="11">{y_value:.1f}</text>',
        ])
    coordinates = " ".join(f"{to_x(x):.2f},{to_y(y):.2f}" for x, y in zip(xs, ys))
    elements.append(f'<polyline points="{coordinates}" fill="none" stroke="#2864dc" stroke-width="3"/>')
    for x, y, point in zip(xs, ys, points):
        cx, cy = to_x(x), to_y(y)
        elements.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="5" fill="#2864dc"/>')
        elements.append(f'<text x="{cx:.2f}" y="{cy - 10:.2f}" text-anchor="middle" font-family="sans-serif" font-size="10">t={point["threshold"]:.2f}</text>')
    elements.append('<text x="450" y="500" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#555">Same GPT-6 Luna outputs (WO-20 prompts A/B); price tiers are portfolio rate proxies, not a model bake-off.</text>')
    elements.append('</svg>')
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def run_experiment() -> dict[str, Any]:
    """Load inputs, fit train-only policies, score held-out cost and quality."""
    examples = load_examples()
    train_indices, test_indices = group_split(examples)
    train_examples = [examples[int(index)] for index in train_indices]
    test_examples = [examples[int(index)] for index in test_indices]
    router = fit_router(examples, train_indices)
    probabilities = router.predict_easy_probability([item.question for item in test_examples])
    route_choices = ["A" if probability >= DEFAULT_ROUTE_THRESHOLD else "B" for probability in probabilities]
    all_a = ["A"] * len(test_examples)
    all_b = ["B"] * len(test_examples)
    premium_baseline = _policy_metrics(test_examples, all_b)
    economy_baseline = _policy_metrics(test_examples, all_a)
    route_only = _policy_metrics(test_examples, route_choices)
    tradeoff = _tradeoff_curve(test_examples, probabilities, premium_baseline)
    semantic_policy = fit_semantic_policy(train_examples)
    semantic_results = evaluate_replay(semantic_policy, test_examples, route_choices)
    safe_cache_hit_ids = set(semantic_results.pop("_safe_hit_ids"))
    false_cache_hit_ids = set(semantic_results.pop("_false_hit_ids"))
    all_cache_hit_ids = safe_cache_hit_ids | false_cache_hit_ids

    uncached_two_pass_cost = sum(
        2 * _tier_cost(item, choice)
        for item, choice in zip(test_examples, route_choices)
    )
    cache_savings = sum(
        _tier_cost(item, choice)
        for item, choice in zip(test_examples, route_choices)
        if item.question_id in all_cache_hit_ids
    )
    cache_policy_cost = uncached_two_pass_cost - cache_savings
    error_impact = _route_error_impact(test_examples, route_choices)
    baseline_f1s = np.asarray([
        answer_f1(item.answer_b, item.answers, item.impossible) for item in test_examples
    ])
    routed_f1s = np.asarray([
        answer_f1(item.answer_a if choice == "A" else item.answer_b, item.answers, item.impossible)
        for item, choice in zip(test_examples, route_choices)
    ])
    delta = routed_f1s - baseline_f1s

    result: dict[str, Any] = {
        "metadata": {
            "dataset": "SQuAD 2.0 dev",
            "dataset_questions": len(examples),
            "dataset_sha256": EXPECTED_SHA256,
            "paired_prediction_rows": len(examples) * 2,
            "train_questions": len(train_examples),
            "test_questions": len(test_examples),
            "train_article_titles": len({item.title for item in train_examples}),
            "test_article_titles": len({item.title for item in test_examples}),
            "split": "GroupShuffleSplit by article title; seed 22021; test_size 0.25",
            "answer_traces": "WO-20 GPT-6 Luna prompt A/B; no additional model calls",
            "router_target": f"Prompt A SQuAD token F1 >= {0.80:.2f}",
            "route_threshold": DEFAULT_ROUTE_THRESHOLD,
            "bootstrap_replicates": BOOTSTRAP_RESAMPLES,
            "price_profiles": {
                "economy": {
                    "source": LOW_COST_PROFILE.source,
                    "input_usd_per_million": LOW_COST_PROFILE.input_usd_per_million,
                    "output_usd_per_million": LOW_COST_PROFILE.output_usd_per_million,
                },
                "premium": {
                    "source": HIGH_COST_PROFILE.source,
                    "input_usd_per_million": HIGH_COST_PROFILE.input_usd_per_million,
                    "output_usd_per_million": HIGH_COST_PROFILE.output_usd_per_million,
                },
            },
            "model_comparison_boundary": "A/B are prompts to the same model, not two distinct LLMs; rate profiles are copied from WO-20 and WO-18.",
        },
        "baselines": {
            "all_economy_prompt_a": economy_baseline,
            "all_premium_prompt_b": premium_baseline,
        },
        "router": {
            "routed": route_only,
            "f1_delta_vs_all_premium": float(np.mean(delta)),
            "f1_delta_bootstrap_95_ci": _bootstrap_mean(delta),
            "errors": error_impact,
            "cutoff_curve": tradeoff,
        },
        "semantic_cache": {
            "calibration": semantic_policy.calibration,
            "heldout_replay": semantic_results,
            "routing_quality_f1": float(route_only["f1"]),
            "routing_plus_cache_quality_f1": float(semantic_results["cache_quality_f1"]),
            "routing_only_two_pass_tiered_cost_usd": float(uncached_two_pass_cost),
            "routing_plus_cache_two_pass_tiered_cost_usd": float(cache_policy_cost),
            "incremental_savings_usd": float(cache_savings),
            "incremental_savings_percent": 100.0 * cache_savings / uncached_two_pass_cost if uncached_two_pass_cost else 0.0,
            "safe_hit_only_savings_usd": float(sum(
                _tier_cost(item, choice)
                for item, choice in zip(test_examples, route_choices)
                if item.question_id in safe_cache_hit_ids
            )),
            "false_hit_count": len(false_cache_hit_ids),
            "cache_compute_cost_included": False,
            "cache_quality_policy": "Second request is a same-context wording variant of the same SQuAD question; reused output is scored against the same gold answers.",
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "experiment_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_svg(tradeoff, RESULTS_DIR / "cost_quality_curve.svg")
    return result


if __name__ == "__main__":
    print(json.dumps(run_experiment(), ensure_ascii=False, indent=2))
