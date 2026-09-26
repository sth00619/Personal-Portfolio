"""Turn measured runs into a category table and inspectable miss candidates."""

import json
from pathlib import Path

from .evaluate import evaluate
from .load import load_scifact, query_category

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def build_report(chosen: str):
    experiments = json.loads((RESULTS / "experiments.json").read_text(encoding="utf-8"))
    runs = json.loads((RESULTS / "runs.json").read_text(encoding="utf-8"))
    corpus, queries, qrels = load_scifact(ROOT / "data" / "scifact")
    if chosen not in runs:
        raise KeyError(chosen)
    lines = ["# Measured SciFact test results", "", f"Documents: {len(corpus)} · judged queries: {len(queries)} · relevant pairs: {sum(map(len, qrels.values()))}", "", "| Configuration | Category | n | Recall@10 | MRR | nDCG@10 |", "|---|---|---:|---:|---:|---:|"]
    for name, categories in experiments["summary"].items():
        for category, row in categories.items():
            lines.append(f"| {name} | {category} | {row['n']} | {row['recall@10']:.4f} | {row['MRR']:.4f} | {row['nDCG@10']:.4f} |")
    (RESULTS / "table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _, per_query = evaluate(runs[chosen], queries, qrels)
    misses = sorted((qid for qid in queries if per_query[qid]["recall@10"] < 1),
                    key=lambda qid: (per_query[qid]["recall@10"], qid))
    candidates = []
    for qid in misses:
        relevant = list(qrels[qid])
        candidates.append({
            "qid": qid, "category": query_category(queries[qid]), "query": queries[qid],
            "recall@10": per_query[qid]["recall@10"],
            "relevant": [{"id": docid, "title": corpus[docid]["title"]} for docid in relevant],
            "top10": [{"id": docid, "title": corpus[docid]["title"]} for docid in runs[chosen][qid][:10]],
        })
    (RESULTS / "miss_candidates.json").write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{chosen}: {len(misses)} queries with incomplete recall@10")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("chosen", help="Configuration name, e.g. hybrid_128")
    build_report(parser.parse_args().chosen)
