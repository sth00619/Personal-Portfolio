"""BM25 retrieval over training-only worked examples for RAG."""

from __future__ import annotations

import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def tokenize(text: str) -> list[str]:
    """Return lowercase word and number tokens for lexical retrieval."""
    return TOKEN_PATTERN.findall(text.lower())


class WorkedExampleRetriever:
    """Retrieve solved GSM8K training examples with BM25 and stable tie order."""

    def __init__(self, examples: Sequence[dict[str, str]]) -> None:
        """Build an index from only the supplied training examples."""
        if not examples:
            raise ValueError("RAG requires at least one training example")
        self.examples = list(examples)
        self.index = BM25Okapi([tokenize(row["question"]) for row in self.examples])

    def retrieve(
        self,
        question: str,
        top_k: int,
        excluded_questions: set[str] | None = None,
    ) -> list[dict[str, str]]:
        """Return the highest-scoring non-identical training examples."""
        if top_k < 1:
            raise ValueError("top_k must be positive")
        excluded = {value.strip().casefold() for value in excluded_questions or set()}
        scores = self.index.get_scores(tokenize(question))
        ranked_indices = sorted(range(len(self.examples)), key=lambda i: (-scores[i], i))
        retrieved: list[dict[str, str]] = []
        for index in ranked_indices:
            row = self.examples[index]
            if row["question"].strip().casefold() in excluded:
                continue
            if not tokenize(question):
                continue
            retrieved.append(row)
            if len(retrieved) == top_k:
                break
        return retrieved

