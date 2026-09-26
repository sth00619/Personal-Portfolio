"""Load BEIR's original SciFact corpus, test queries, and graded qrels."""

import csv
import json
import re
from pathlib import Path


def load_scifact(folder: Path):
    def load_jsonl(name):
        with (folder / name).open(encoding="utf-8") as stream:
            return {str(row["_id"]): row for line in stream if (row := json.loads(line))}

    corpus = load_jsonl("corpus.jsonl")
    all_queries = load_jsonl("queries.jsonl")
    qrels = {}
    with (folder / "qrels" / "test.tsv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            score = int(row["score"])
            if score > 0:
                qrels.setdefault(row["query-id"], {})[row["corpus-id"]] = score
    queries = {qid: all_queries[qid]["text"] for qid in qrels}
    assert queries and all(qrels[qid] for qid in queries)
    return corpus, queries, qrels


NEGATION = re.compile(r"\b(no|not|never|without|cannot|doesn't|don't|isn't|aren't|lack|lacks|negative|unrelated)\b", re.I)
NUMERIC = re.compile(r"\b\d+(?:\.\d+)?\b|\b(percent|percentage|fold|rate|higher|lower|increase|decrease)\b", re.I)


def query_category(text: str) -> str:
    """Mutually exclusive query-form buckets, not labels supplied by SciFact."""
    if NEGATION.search(text):
        return "negation"
    if NUMERIC.search(text):
        return "numeric_or_comparative"
    return "other"
