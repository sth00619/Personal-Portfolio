"""Render measured retrieval and generation results as Markdown."""

import json
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIRECTORY = PROJECT_ROOT / "results"


def build_report() -> None:
    """Create a compact stage table and representative cited answers."""
    experiment = cast(
        dict[str, object],
        json.loads((RESULTS_DIRECTORY / "experiments.json").read_text(encoding="utf-8")),
    )
    answers = cast(
        list[dict[str, object]],
        json.loads((RESULTS_DIRECTORY / "answers.json").read_text(encoding="utf-8")),
    )
    retrieval = cast(dict[str, dict[str, float | int]], experiment["retrieval"])
    lines = [
        "# WO-02 measured results",
        "",
        "| Stage | n | Recall@10 | MRR | nDCG@10 |",
        "|---|---:|---:|---:|---:|",
    ]
    for stage, metrics in retrieval.items():
        lines.append(
            f"| {stage} | {metrics['n']} | {float(metrics['recall@10']):.4f} | "
            f"{float(metrics['MRR']):.4f} | {float(metrics['nDCG@10']):.4f} |"
        )
    generation = cast(dict[str, object], experiment["generation"])
    lines.extend(
        [
            "",
            "## Generation metrics (reported separately)",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Citation coverage | {float(generation['citation_coverage']):.4f} |",
            f"| Citation correctness | {float(generation['citation_correctness']):.4f} |",
            f"| Extractive grounding | {float(generation['extractive_grounding']):.4f} |",
            f"| Faithfulness | {float(generation['faithfulness']):.4f} |",
            f"| Answer relevance cosine | {float(generation['answer_relevance_cosine']):.4f} |",
            f"| Verdict accuracy | {float(generation['verdict_accuracy']):.4f} |",
            "",
            "## Cited answer examples",
            "",
        ]
    )
    represented: set[str] = set()
    successful = [
        answer
        for answer in answers
        if answer["expected_label"] == answer["predicted_label"]
        and str(answer["citation"]).split("#", maxsplit=1)[0]
        in cast(list[str], answer["relevant_doc_ids"])
    ]
    for answer in successful:
        question_type = str(answer["question_type"])
        if question_type in represented:
            continue
        represented.add(question_type)
        lines.extend(
            [
                f"### {question_type}",
                "",
                f"- Claim: {answer['claim']}",
                f"- Answer: {answer['answer']}",
                f"- Gold / predicted: {answer['expected_label']} / {answer['predicted_label']}",
                "",
            ]
        )
    (RESULTS_DIRECTORY / "report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Build the Markdown report from the latest JSON artifacts."""
    build_report()


if __name__ == "__main__":
    main()
