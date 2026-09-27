"""Typed records shared by the semantic-cache benchmark."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CacheContext:
    """Fields that isolate a cached answer from unsafe reuse."""

    model: str
    temperature: float
    tools: tuple[str, ...]
    system_prompt_version: str
    tenant_id: str
    customer_tier: str

    def to_dict(self) -> dict[str, object]:
        """Convert the context to a stable serializable mapping."""
        return asdict(self)


@dataclass(frozen=True)
class QuestionPair:
    """One human-labeled Quora question pair."""

    question1: str
    question2: str
    label_duplicate: bool
    safe_to_reuse: bool


@dataclass(frozen=True)
class ReplayEvent:
    """One request in the deterministic 1,000-query replay."""

    event_id: int
    pair_id: int
    question: str
    intent_id: str
    request_kind: str
    context: CacheContext


@dataclass(frozen=True)
class CachedAnswer:
    """Response payload stored in exact and semantic caches."""

    answer: str
    intent_id: str


@dataclass(frozen=True)
class CacheLookup:
    """The cache tier selected before an LLM invocation."""

    level: str
    cached_answer: CachedAnswer | None
    similarity: float | None


@dataclass(frozen=True)
class ReplayRecord:
    """Measured outcome for one replayed request."""

    event_id: int
    pair_id: int
    request_kind: str
    cache_level: str
    valid_hit: bool | None
    similarity: float | None
    baseline_cost_usd: float
    actual_cost_usd: float
    baseline_latency_ms: float
    actual_latency_ms: float

    def to_dict(self) -> dict[str, object]:
        """Convert a replay result to a JSON-serializable mapping."""
        return asdict(self)
