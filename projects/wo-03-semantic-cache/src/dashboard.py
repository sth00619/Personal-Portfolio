"""Render recruiter-readable semantic-cache result artifacts."""

import csv
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt

DASHBOARD_DPI = 160
PERCENT_SCALE = 100.0


def write_curve_csv(
    path: Path, curve: Sequence[dict[str, float | int]]
) -> None:
    """Persist the complete threshold precision curve as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "threshold",
        "precision",
        "recall",
        "false_hit_rate",
        "coverage",
        "true_hits",
        "false_hits",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(curve)


def render_precision_curve(
    path: Path,
    curve: Sequence[dict[str, float | int]],
    selected_threshold: float,
) -> None:
    """Render precision, recall, and coverage against semantic threshold."""
    thresholds = [float(row["threshold"]) for row in curve]
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.plot(thresholds, [float(row["precision"]) for row in curve], label="Precision")
    axis.plot(thresholds, [float(row["recall"]) for row in curve], label="Recall")
    axis.plot(thresholds, [float(row["coverage"]) for row in curve], label="Coverage")
    axis.axvline(selected_threshold, color="#d62728", linestyle="--", label=f"Selected {selected_threshold:.3f}")
    axis.axhline(0.995, color="#777777", linestyle=":", label="99.5% precision gate")
    axis.set(xlabel="Cosine similarity threshold", ylabel="Rate", ylim=(0.0, 1.03))
    axis.set_title("Semantic cache threshold trade-off (2,000 held-out labeled pairs)")
    axis.grid(alpha=0.25)
    axis.legend(loc="lower left")
    figure.tight_layout()
    figure.savefig(path, dpi=DASHBOARD_DPI)
    plt.close(figure)


def render_dashboard(
    path: Path,
    replay: dict[str, object],
    selected_threshold: float,
) -> None:
    """Render a single-image dashboard with Ship Gate KPIs and trade-offs."""
    hit_counts = dict(replay["hit_counts"])
    figure = plt.figure(figsize=(16, 9), facecolor="#f5f7fb")
    grid = figure.add_gridspec(2, 3, top=0.77, bottom=0.13, hspace=0.36, wspace=0.28)
    figure.suptitle("WO-03 · Semantic Cache Replay Dashboard", fontsize=24, fontweight="bold", y=0.96)
    figure.text(
        0.5,
        0.91,
        "1,000 Quora-derived requests · Redis exact/prefix + FAISS semantic cache",
        ha="center",
        fontsize=12,
        color="#4b5563",
    )
    kpis = [
        ("Response hit rate", f"{float(replay['response_hit_rate']) * PERCENT_SCALE:.1f}%"),
        ("Semantic false hits", f"{float(replay['semantic_false_hit_rate']) * PERCENT_SCALE:.2f}%"),
        ("Cost reduction", f"{float(replay['cost_reduction_rate']) * PERCENT_SCALE:.1f}%"),
        ("p95 reduction", f"{float(replay['p95_reduction_rate']) * PERCENT_SCALE:.1f}%"),
    ]
    for index, (label, value) in enumerate(kpis):
        left = 0.07 + index * 0.23
        figure.text(left, 0.84, value, fontsize=22, fontweight="bold", color="#0f4c81")
        figure.text(left, 0.80, label, fontsize=10, color="#4b5563")

    hit_axis = figure.add_subplot(grid[0, 0])
    levels = ["exact", "semantic", "prefix", "miss"]
    counts = [int(hit_counts.get(level, 0)) for level in levels]
    hit_bars = hit_axis.bar(
        levels, counts, color=["#1f77b4", "#2ca02c", "#ffbf00", "#9ca3af"]
    )
    hit_axis.bar_label(hit_bars, padding=3)
    hit_axis.set_title("Requests by cache tier")
    hit_axis.set_ylabel("Requests")
    hit_axis.grid(axis="y", alpha=0.2)

    cost_axis = figure.add_subplot(grid[0, 1])
    costs = [float(replay["baseline_cost_usd"]), float(replay["actual_cost_usd"])]
    cost_axis.bar(["No cache", "3-tier cache"], costs, color=["#9ca3af", "#2ca02c"])
    cost_axis.set_title("Modeled API cost")
    cost_axis.set_ylabel("USD / 1,000 requests")
    cost_axis.grid(axis="y", alpha=0.2)

    latency_axis = figure.add_subplot(grid[0, 2])
    labels = ["p50", "p95"]
    baseline = [float(replay["baseline_p50_ms"]), float(replay["baseline_p95_ms"])]
    actual = [float(replay["actual_p50_ms"]), float(replay["actual_p95_ms"])]
    positions = [0.0, 1.0]
    latency_axis.bar([value - 0.18 for value in positions], baseline, width=0.36, label="No cache", color="#9ca3af")
    latency_axis.bar([value + 0.18 for value in positions], actual, width=0.36, label="3-tier", color="#1f77b4")
    latency_axis.set_xticks(positions, labels)
    latency_axis.set_title("Modeled latency")
    latency_axis.set_ylabel("Milliseconds")
    latency_axis.legend()
    latency_axis.grid(axis="y", alpha=0.2)

    decision_axis = figure.add_subplot(grid[1, :2])
    decision_axis.axis("off")
    saved = float(replay["cost_saved_usd"])
    decision_text = (
        f"Decision: cosine threshold {selected_threshold:.3f}\n\n"
        f"• Semantic precision: {float(replay['semantic_precision']) * PERCENT_SCALE:.2f}% "
        f"({int(replay['semantic_false_hits'])} false / {int(replay['semantic_hits'])} hits)\n"
        f"• Cache-assisted requests: {float(replay['cache_assist_rate']) * PERCENT_SCALE:.1f}%\n"
        f"• Modeled saving: ${saved:.4f} per 1,000 requests\n"
        "• Prompt version and tenant context are included in response keys"
    )
    decision_axis.text(
        0.02,
        0.9,
        decision_text,
        va="top",
        fontsize=14,
        linespacing=1.6,
        bbox={"boxstyle": "round,pad=0.8", "facecolor": "white", "edgecolor": "#d1d5db"},
    )

    caveat_axis = figure.add_subplot(grid[1, 2])
    caveat_axis.axis("off")
    caveat_axis.text(
        0.02,
        0.9,
        "Measurement boundary\n\n"
        "Redis and FAISS hits are real.\n"
        "LLM price and latency are a\n"
        "deterministic workload model,\n"
        "not a provider benchmark.\n\n"
        "Human QQP labels judge whether\n"
        "a semantic response is safe to reuse.",
        va="top",
        fontsize=12,
        linespacing=1.45,
        color="#374151",
    )
    figure.text(
        0.5,
        0.045,
        "Response cache hits avoid generation; prefix hits reduce modeled prefill cost and latency.",
        ha="center",
        fontsize=10,
        color="#6b7280",
    )
    figure.savefig(path, dpi=DASHBOARD_DPI, facecolor=figure.get_facecolor())
    plt.close(figure)


def render_dashboard_html(
    path: Path,
    replay: dict[str, object],
    selected_threshold: float,
) -> None:
    """Write a portable HTML summary that links the generated plots."""
    false_rate = float(replay["semantic_false_hit_rate"]) * PERCENT_SCALE
    response_hit = float(replay["response_hit_rate"]) * PERCENT_SCALE
    cost_reduction = float(replay["cost_reduction_rate"]) * PERCENT_SCALE
    p95_reduction = float(replay["p95_reduction_rate"]) * PERCENT_SCALE
    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WO-03 Semantic Cache Dashboard</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fb; color: #172033; }}
main {{ max-width: 1100px; margin: 40px auto; padding: 0 24px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
.card {{ background: white; border-radius: 14px; padding: 20px; box-shadow: 0 5px 20px #17203312; }}
.value {{ font-size: 2rem; font-weight: 750; color: #0f4c81; }}
img {{ width: 100%; border-radius: 14px; margin-top: 24px; }}
small {{ color: #5f6b7a; }}
</style>
<main>
<h1>WO-03 · Semantic Cache Replay</h1>
<p>1,000 Quora-derived requests · selected cosine threshold {selected_threshold:.3f}</p>
<section class="grid">
<div class="card"><div class="value">{response_hit:.1f}%</div>Response hit rate</div>
<div class="card"><div class="value">{false_rate:.2f}%</div>Semantic false-hit rate</div>
<div class="card"><div class="value">{cost_reduction:.1f}%</div>Modeled cost reduction</div>
<div class="card"><div class="value">{p95_reduction:.1f}%</div>Modeled p95 reduction</div>
</section>
<img src="dashboard.png" alt="Semantic cache KPI dashboard">
<img src="precision_curve.png" alt="Threshold precision curve">
<p><small>Redis and FAISS cache behavior is executed. LLM price and latency use a deterministic simulation and are not provider measurements.</small></p>
</main>
</html>
"""
    path.write_text(html, encoding="utf-8")
