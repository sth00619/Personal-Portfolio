"""Build a compact Markdown report from measured benchmark results."""

from pathlib import Path

PERCENT_SCALE = 100.0


def build_report(path: Path, experiment: dict[str, object]) -> None:
    """Write Ship Gate metrics, tier counts, and cache-bust evidence."""
    replay = dict(experiment["replay"])
    threshold = dict(experiment["threshold_tuning"])
    cache_bust = dict(experiment["cache_bust"])
    hit_counts = dict(replay["hit_counts"])
    lines = [
        "# WO-03 measured results",
        "",
        "## Replay KPIs",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Queries | {int(replay['queries']):,} |",
        f"| Response hit rate | {float(replay['response_hit_rate']) * PERCENT_SCALE:.2f}% |",
        f"| Cache assist rate | {float(replay['cache_assist_rate']) * PERCENT_SCALE:.2f}% |",
        f"| Semantic false-hit rate | {float(replay['semantic_false_hit_rate']) * PERCENT_SCALE:.2f}% |",
        f"| Modeled cost reduction | {float(replay['cost_reduction_rate']) * PERCENT_SCALE:.2f}% |",
        f"| Modeled p50 reduction | {float(replay['p50_reduction_rate']) * PERCENT_SCALE:.2f}% |",
        f"| Modeled p95 reduction | {float(replay['p95_reduction_rate']) * PERCENT_SCALE:.2f}% |",
        "",
        "## Cache tier counts",
        "",
        "| Tier | Requests |",
        "|---|---:|",
    ]
    for level in ("exact", "semantic", "prefix", "miss"):
        lines.append(f"| {level} | {int(hit_counts.get(level, 0))} |")
    lines.extend(
        [
            "",
            "## Threshold decision",
            "",
            f"Selected cosine threshold: **{float(threshold['selected_threshold']):.3f}**",
            "",
            f"Validation precision: {float(threshold['selected_precision']) * PERCENT_SCALE:.2f}%",
            f"Validation recall: {float(threshold['selected_recall']) * PERCENT_SCALE:.2f}%",
            f"Validation false hits: {int(threshold['selected_false_hits'])}",
            "",
            "## Prompt-version cache bust",
            "",
            f"1. First v1 request: `{cache_bust['first_v1_lookup']}`",
            f"2. Repeated v1 request: `{cache_bust['second_v1_lookup']}`",
            f"3. Same request after switching to v2: `{cache_bust['first_v2_lookup']}`",
            f"4. Explicit v1 invalidation removed: `{cache_bust['invalidated']}`",
            "",
            "> Redis and FAISS behavior is executed. Cost and latency values come from the documented deterministic LLM workload model, not a live provider benchmark.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
