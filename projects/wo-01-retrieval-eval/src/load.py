"""Load BEIR's original SciFact corpus, test queries, and graded qrels."""

import csv
import json
import re
from pathlib import Path
from typing import TypeAlias, cast

CorpusDocument: TypeAlias = dict[str, object]
Corpus: TypeAlias = dict[str, CorpusDocument]
Queries: TypeAlias = dict[str, str]
Qrels: TypeAlias = dict[str, dict[str, int]]

NEGATION = re.compile(
    r"\b(no|not|never|without|cannot|doesn't|don't|isn't|aren't|lack|lacks|negative|unrelated)\b",
    re.IGNORECASE,
)
NUMERIC = re.compile(
    (
        r"\b\d+(?:\.\d+)?\b|\b(percent|percentage|fold|rate|high|higher|low|lower|"
        r"more|less|fewer|increase|decrease)\b"
    ),
    re.IGNORECASE,
)


def _load_jsonl(path: Path) -> dict[str, dict[str, object]]:
    """Load JSON Lines rows keyed by their required ``_id`` field."""
    rows: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = cast(dict[str, object], json.loads(line))
            rows[str(row["_id"])] = row
    return rows


def load_scifact(folder: Path) -> tuple[Corpus, Queries, Qrels]:
    """Return the SciFact corpus and only the queries judged in the test qrels."""
    corpus = _load_jsonl(folder / "corpus.jsonl")
    all_queries = _load_jsonl(folder / "queries.jsonl")
    qrels: Qrels = {}
    with (folder / "qrels" / "test.tsv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            score = int(row["score"])
            if score > 0:
                qrels.setdefault(row["query-id"], {})[row["corpus-id"]] = score
    queries = {qid: str(all_queries[qid]["text"]) for qid in qrels}
    if not queries or not all(qrels[qid] for qid in queries):
        raise ValueError("SciFact test data has no judged queries")
    return corpus, queries, qrels


def query_category(text: str) -> str:
    """Assign a mutually exclusive query-form bucket derived from claim text."""
    if NEGATION.search(text):
        return "negation"
    if NUMERIC.search(text):
        return "numeric_or_comparative"
    return "other"
