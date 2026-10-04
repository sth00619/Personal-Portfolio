"""Persist auditable replay evidence and a dependency-free cost chart."""

import json
from pathlib import Path
from typing import Any

CHART_WIDTH = 1100
CHART_HEIGHT = 680
BAR_WIDTH = 22
BAR_GAP = 11
CHART_LEFT = 80
CHART_TOP = 95
CHART_BOTTOM = 540


def write_results(output_dir: Path, results: dict[str, Any]) -> None:
    """Write JSON, Markdown summary, and one SVG bar per case."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "experiment.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    cases = results["cases"]
    lines = [
        "# WO-04 measured deterministic replay",
        "",
        f"- Cases: **{len(cases)}**; correct terminal labels: **{results['correct_count']}/{len(cases)}**",
        f"- Reviewer returns: **{results['reviewer_return_count']}**",
        f"- Scripted human approvals: **{results['approval_count']}**; payouts: **{results['payout_count']}**",
        f"- Maximum modeled cost: **${results['max_cost_usd']:.6f}**; cap: **${results['cost_cap_usd']:.6f}**",
        f"- Resume demo: **{results['resume_demo']['same_terminal']}** with same terminal "
        f"`{results['resume_demo']['terminal']}`",
        "",
        "Cost and token usage are deterministic estimates for simulated workers; no LLM API was called. "
        "Redis snapshots, approval gate, and payout record are executed for real.",
        "",
        "| Case | Gold | Terminal | Steps | Returns | Modeled cost (USD) | Path |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for item in cases:
        lines.append(
            f"| {item['case_id']} | {item['gold_terminal']} | {item['terminal']} | "
            f"{item['steps']} | {item['reviewer_returns']} | ${item['cost_usd']:.6f} | "
            f"{' → '.join(item['path'])} |"
        )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "cost_chart.svg").write_text(_cost_svg(cases, results["cost_cap_usd"]), encoding="utf-8")


def _cost_svg(cases: list[dict[str, Any]], cap: float) -> str:
    """Render one modeled-cost bar per case with the enforced cap visible."""
    max_value = cap * 1.08
    height = CHART_BOTTOM - CHART_TOP
    baseline = CHART_BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_WIDTH}" height="{CHART_HEIGHT}" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="80" y="45" font-size="25" font-family="Arial" fill="#0f172a">WO-04 · Modeled cost per synthetic case</text>',
        '<text x="80" y="73" font-size="14" font-family="Arial" fill="#475569">Executed Redis workflow · fixed token estimates · no LLM API charges</text>',
    ]
    for index in range(6):
        value = cap * index / 5
        y = baseline - value / max_value * height
        parts.append(f'<line x1="80" y1="{y:.1f}" x2="1080" y2="{y:.1f}" stroke="#cbd5e1"/>')
        parts.append(f'<text x="7" y="{y + 5:.1f}" font-size="12" font-family="Arial" fill="#334155">${value:.4f}</text>')
    for index, item in enumerate(cases):
        x = CHART_LEFT + index * (BAR_WIDTH + BAR_GAP)
        bar_height = item["cost_usd"] / max_value * height
        y = baseline - bar_height
        color = {"PAID": "#2563eb", "DENIED": "#dc2626", "NEEDS_INFO": "#d97706"}.get(
            item["terminal"], "#64748b"
        )
        parts.append(f'<rect x="{x}" y="{y:.1f}" width="{BAR_WIDTH}" height="{bar_height:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{x + 4}" y="563" font-size="9" font-family="Arial" fill="#334155" transform="rotate(55 {x + 4} 563)">{item["case_id"]}</text>')
    cap_y = baseline - cap / max_value * height
    parts.append(f'<line x1="80" y1="{cap_y:.1f}" x2="1080" y2="{cap_y:.1f}" stroke="#111827" stroke-width="2" stroke-dasharray="7 5"/>')
    parts.append('<text x="80" y="642" font-size="13" font-family="Arial" fill="#334155">Blue: paid · Red: denied · Amber: needs information · Dashed line: enforced $0.005 cap</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
