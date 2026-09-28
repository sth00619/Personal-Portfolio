"""Shared typed records for retrieval, generation, and evaluation."""

from dataclasses import asdict, dataclass
from typing import TypeAlias

CorpusDocument: TypeAlias = dict[str, object]
Corpus: TypeAlias = dict[str, CorpusDocument]
Queries: TypeAlias = dict[str, str]
Qrels: TypeAlias = dict[str, dict[str, int]]
Run: TypeAlias = dict[str, list[str]]


@dataclass(frozen=True)
class Chunk:
    """One indexed text unit with a stable parent document reference."""

    chunk_id: str
    doc_id: str
    text: str


@dataclass(frozen=True)
class SearchHit:
    """One ranked document represented by its strongest source chunk."""

    chunk_id: str
    doc_id: str
    text: str
    score: float


@dataclass(frozen=True)
class EvalQuestion:
    """A deterministic question backed by a human-labeled SciFact claim."""

    query_id: str
    question_type: str
    question: str
    claim: str
    expected_label: str
    relevant_doc_ids: tuple[str, ...]


@dataclass(frozen=True)
class GroundedAnswer:
    """A verdict plus an extractive rationale and explicit source chunk."""

    query_id: str
    question_type: str
    expected_label: str
    predicted_label: str
    claim: str
    answer: str
    rationale: str
    citation: str
    citation_text: str
    confidence: float
    relevant_doc_ids: tuple[str, ...]
    retrieved_doc_ids: tuple[str, ...]
    relevant_rank: int | None

    def to_dict(self) -> dict[str, object]:
        """Convert the immutable answer to a JSON-serializable mapping."""
        return asdict(self)
