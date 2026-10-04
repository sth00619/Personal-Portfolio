"""Render attack outcomes, false-positive rates, and auditable evidence."""

import json
from pathlib import Path
from typing import Any

CHART_WIDTH = 1120
CHART_HEIGHT = 620
PLOT_TOP = 130
PLOT_BOTTOM = 475
BASELINE_COLOR = "#dc2626"
GUARDED_COLOR = "#2563eb"
ALERT_COLOR = "#d97706"


def write_results(output_dir: Path, results: dict[str, Any]) -> None:
    """Save machine-readable data, readable tables, SVG, and all audit events."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "experiment.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    audit_lines = [json.dumps(event, sort_keys=True) for event in results["audit_events"]]
    (output_dir / "audit.jsonl").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(_markdown(results), encoding="utf-8")
    (output_dir / "comparison.svg").write_text(_chart(results), encoding="utf-8")


def _markdown(results: dict[str, Any]) -> str:
    """Produce a compact report with attack success and benign alerts adjacent."""
    lines = [
        "# WO-05 synthetic red-team results",
        "",
        "| Measure | Unguarded | Legacy guard v1 | Final guard v2 |",
        "|---|---:|---:|---:|",
        f"| Attack success, 60 attempts | {results['baseline_success']}/60 "
        f"({results['baseline_rate']:.1%}) | {results['legacy_success']}/60 "
        f"({results['legacy_rate']:.1%}) | {results['guarded_success']}/60 "
        f"({results['guarded_rate']:.1%}) |",
        f"| Benign classifier false positives, 100 resumes | — | — | "
        f"{results['benign_flagged']}/100 ({results['false_positive_rate']:.1%}) |",
        f"| Benign evaluation completed | — | — | {results['benign_completed']}/100 |",
        "",
        f"The phrase classifier alerted on **{results['attack_classifier_alerts']}/60** attacks and missed "
        f"**{results['attack_count'] - results['attack_classifier_alerts']}**. It only alerts; "
        "the trust boundary and tool router enforce behavior after a proposed action.",
        "",
        "## By attack family",
        "",
        "| Entry point | Attempts | Unguarded success | Guarded success | Classifier alerts |",
        "|---|---:|---:|---:|---:|",
    ]
    for family, stats in results["by_family"].items():
        lines.append(
            f"| {family} | {stats['count']} | {stats['baseline_success']}/{stats['count']} "
            f"({stats['baseline_rate']:.1%}) | {stats['guarded_success']}/{stats['count']} "
            f"({stats['guarded_rate']:.1%}) | {stats['classifier_alerts']}/{stats['count']} |"
        )
    lines += [
        "",
        "## By attacker objective",
        "",
        "| Objective | Attempts | Unguarded success | Guarded success |",
        "|---|---:|---:|---:|",
    ]
    for goal, stats in results["by_goal"].items():
        lines.append(
            f"| {goal} | {stats['count']} | {stats['baseline_success']}/{stats['count']} | "
            f"{stats['guarded_success']}/{stats['count']} |"
        )
    lines += [
        "",
        "## Enforced rule events",
        "",
    ]
    for rule, count in sorted(results["blocked_rule_counts"].items()):
        lines.append(f"- `{rule}`: {count} events")
    lines += [
        "",
        "## Discovered bypass and repair",
        "",
        f"- Case: `{results['bypass']['attack_id']}`",
        f"- Old guard: score became **{results['bypass']['legacy_score']}** from numeric PDF metadata.",
        f"- Final guard: score stayed at rubric value **{results['bypass']['guarded_score']}**; "
        f"rules: {', '.join(results['bypass']['blocked_rules'])}.",
        "- The input classifier did not flag this text-free hint. The protected tool route rejected "
        "untrusted score provenance, so the defense does not depend on a phrase match.",
        "",
        "## Measurement boundary",
        "",
        "The planner and tools are deterministic mocks; no LLM API, real email, or ATS write was used. "
        "Attack success is measured from mock side effects. The 60 cases were authored for this "
        "harness, so these percentages are control-flow results on this corpus, not a live-model "
        "security guarantee. `audit.jsonl` contains one rule-coded event per alert or block.",
        "",
    ]
    return "\n".join(lines)


def _chart(results: dict[str, Any]) -> str:
    """Draw before/after family bars and the benign false-positive bar."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="70" y="45" font-size="26" font-family="Arial" fill="#0f172a">WO-05 · Prompt injection control-flow benchmark</text>',
        '<text x="70" y="75" font-size="15" font-family="Arial" fill="#475569">60 synthetic attacks · 100 benign resumes · deterministic mock agent and tools</text>',
    ]
    for percent in (0, 25, 50, 75, 100):
        y = PLOT_BOTTOM - (PLOT_BOTTOM - PLOT_TOP) * percent / 100
        parts.append(f'<line x1="70" y1="{y:.1f}" x2="1060" y2="{y:.1f}" stroke="#cbd5e1"/>')
        parts.append(f'<text x="23" y="{y + 5:.1f}" font-size="13" font-family="Arial" fill="#334155">{percent}%</text>')
    groups = list(results["by_family"].items())
    for index, (family, stats) in enumerate(groups):
        center = 205 + index * 260
        before = stats["baseline_rate"] * (PLOT_BOTTOM - PLOT_TOP)
        after = stats["guarded_rate"] * (PLOT_BOTTOM - PLOT_TOP)
        parts.append(f'<rect x="{center - 65}" y="{PLOT_BOTTOM - before:.1f}" width="60" height="{before:.1f}" fill="{BASELINE_COLOR}"/>')
        parts.append(f'<rect x="{center + 5}" y="{PLOT_BOTTOM - after:.1f}" width="60" height="{after:.1f}" fill="{GUARDED_COLOR}"/>')
        parts.append(f'<text x="{center - 47}" y="{PLOT_BOTTOM - before - 9:.1f}" font-size="15" font-family="Arial" fill="#7f1d1d">{stats["baseline_rate"]:.0%}</text>')
        parts.append(f'<text x="{center + 22}" y="{PLOT_BOTTOM - after - 9:.1f}" font-size="15" font-family="Arial" fill="#1e3a8a">{stats["guarded_rate"]:.0%}</text>')
        parts.append(f'<text x="{center - 53}" y="505" font-size="17" font-family="Arial" fill="#0f172a">{family}</text>')
    center = 985
    fpr = results["false_positive_rate"] * (PLOT_BOTTOM - PLOT_TOP)
    parts.append(f'<rect x="{center - 30}" y="{PLOT_BOTTOM - fpr:.1f}" width="60" height="{fpr:.1f}" fill="{ALERT_COLOR}"/>')
    parts.append(f'<text x="{center - 12}" y="{PLOT_BOTTOM - fpr - 9:.1f}" font-size="15" font-family="Arial" fill="#92400e">{results["false_positive_rate"]:.0%}</text>')
    parts.append('<text x="930" y="505" font-size="16" font-family="Arial" fill="#0f172a">benign FPR</text>')
    parts.append(f'<rect x="70" y="550" width="17" height="17" fill="{BASELINE_COLOR}"/>')
    parts.append('<text x="94" y="564" font-size="14" font-family="Arial">Unguarded attack success</text>')
    parts.append(f'<rect x="320" y="550" width="17" height="17" fill="{GUARDED_COLOR}"/>')
    parts.append('<text x="344" y="564" font-size="14" font-family="Arial">Guarded attack success</text>')
    parts.append(f'<rect x="560" y="550" width="17" height="17" fill="{ALERT_COLOR}"/>')
    parts.append('<text x="584" y="564" font-size="14" font-family="Arial">Benign classifier alert</text>')
    parts.append('<text x="70" y="595" font-size="12" font-family="Arial" fill="#475569">Synthetic benchmark only: percentages do not estimate live LLM resistance.</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
