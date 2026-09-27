"""Three-tier exact, semantic, and static-prefix cache implementation."""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Iterable, Protocol

import faiss
import numpy as np
from numpy.typing import NDArray

from .models import CacheContext, CachedAnswer, CacheLookup

CACHE_NAMESPACE = "wo03"
DEFAULT_TTL_SECONDS = 3_600


class RedisClient(Protocol):
    """Redis operations required by the cache without tying tests to a server."""

    def get(self, key: str) -> bytes | str | None:
        """Read a value by key."""
        ...

    def setex(self, key: str, ttl_seconds: int, value: str) -> object:
        """Write a value with a TTL."""
        ...

    def scan_iter(self, match: str) -> Iterable[bytes | str]:
        """Yield keys matching a glob pattern."""
        ...

    def delete(self, *keys: bytes | str) -> int:
        """Delete one or more keys."""
        ...


@dataclass(frozen=True)
class SemanticEntry:
    """Metadata aligned with one FAISS vector row."""

    question: str
    cached_answer: CachedAnswer
    expires_at: float


def normalize_question(question: str) -> str:
    """Normalize casing and whitespace for exact cache keys."""
    return " ".join(question.casefold().split())


def _digest(value: object) -> str:
    """Hash a JSON-serializable value into a compact stable key component."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def answer_scope_key(context: CacheContext) -> str:
    """Return the response-cache scope including tenant and policy context."""
    return _digest(context.to_dict())


def prefix_scope_key(context: CacheContext) -> str:
    """Return a safe static-prefix scope shared only within one customer tier."""
    return _digest(
        {
            "model": context.model,
            "temperature": context.temperature,
            "tools": context.tools,
            "system_prompt_version": context.system_prompt_version,
            "customer_tier": context.customer_tier,
        }
    )


class ExactCache:
    """Redis-backed exact response cache with TTL and versioned keys."""

    def __init__(self, client: RedisClient, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """Store the Redis client and default expiration period."""
        self.client = client
        self.ttl_seconds = ttl_seconds

    def _key(self, question: str, context: CacheContext) -> str:
        """Build a version-readable exact response key."""
        question_hash = _digest(normalize_question(question))
        return (
            f"{CACHE_NAMESPACE}:exact:{context.system_prompt_version}:"
            f"{answer_scope_key(context)}:{question_hash}"
        )

    def get(self, question: str, context: CacheContext) -> CachedAnswer | None:
        """Return an unexpired exact response when present."""
        raw = self.client.get(self._key(question, context))
        if raw is None:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        payload = json.loads(text)
        return CachedAnswer(answer=str(payload["answer"]), intent_id=str(payload["intent_id"]))

    def set(self, question: str, context: CacheContext, value: CachedAnswer) -> None:
        """Cache one response using Redis expiration."""
        payload = json.dumps(
            {"answer": value.answer, "intent_id": value.intent_id},
            sort_keys=True,
        )
        self.client.setex(self._key(question, context), self.ttl_seconds, payload)


class PrefixCache:
    """Redis-backed record of reusable static system-prompt prefixes."""

    def __init__(self, client: RedisClient, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """Store the Redis client and prefix expiration period."""
        self.client = client
        self.ttl_seconds = ttl_seconds

    def _key(self, context: CacheContext) -> str:
        """Build a policy-versioned prefix cache key."""
        return (
            f"{CACHE_NAMESPACE}:prefix:{context.system_prompt_version}:"
            f"{prefix_scope_key(context)}"
        )

    def contains(self, context: CacheContext) -> bool:
        """Check whether the static prompt prefix is warm."""
        return self.client.get(self._key(context)) is not None

    def set(self, context: CacheContext) -> None:
        """Mark one static prompt prefix as warm."""
        self.client.setex(self._key(context), self.ttl_seconds, "warm")


class SemanticCache:
    """Tenant-isolated FAISS cosine indexes with explicit TTL handling."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """Create empty per-scope indexes and metadata registries."""
        self.ttl_seconds = ttl_seconds
        self.entries: dict[str, list[SemanticEntry]] = {}
        self.vectors: dict[str, list[NDArray[np.float32]]] = {}
        self.indexes: dict[str, faiss.IndexFlatIP] = {}
        self.scope_versions: dict[str, str] = {}

    def _rebuild(self, scope: str, now: float) -> None:
        """Drop expired rows and rebuild the scope's exact cosine index."""
        old_entries = self.entries.get(scope, [])
        old_vectors = self.vectors.get(scope, [])
        kept = [
            (entry, vector)
            for entry, vector in zip(old_entries, old_vectors)
            if entry.expires_at > now
        ]
        self.entries[scope] = [entry for entry, _vector in kept]
        self.vectors[scope] = [vector for _entry, vector in kept]
        if not kept:
            self.indexes.pop(scope, None)
            return
        matrix = np.vstack(self.vectors[scope]).astype(np.float32)
        index = faiss.IndexFlatIP(int(matrix.shape[1]))
        index.add(matrix)
        self.indexes[scope] = index

    def add(
        self,
        question: str,
        context: CacheContext,
        vector: NDArray[np.float32],
        value: CachedAnswer,
        now: float | None = None,
    ) -> None:
        """Add one normalized embedding and aligned answer metadata."""
        timestamp = time.time() if now is None else now
        scope = answer_scope_key(context)
        normalized = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(normalized)
        self.entries.setdefault(scope, []).append(
            SemanticEntry(question, value, timestamp + self.ttl_seconds)
        )
        self.vectors.setdefault(scope, []).append(normalized[0].copy())
        self.scope_versions[scope] = context.system_prompt_version
        self._rebuild(scope, timestamp)

    def search(
        self,
        context: CacheContext,
        vector: NDArray[np.float32],
        threshold: float,
        now: float | None = None,
    ) -> tuple[CachedAnswer, float] | None:
        """Return the nearest in-scope answer only when similarity clears threshold."""
        timestamp = time.time() if now is None else now
        scope = answer_scope_key(context)
        self._rebuild(scope, timestamp)
        index = self.indexes.get(scope)
        if index is None:
            return None
        query = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(query)
        scores, indices = index.search(query, 1)
        score = float(scores[0, 0])
        if int(indices[0, 0]) < 0 or score < threshold:
            return None
        entry = self.entries[scope][int(indices[0, 0])]
        return entry.cached_answer, score

    def invalidate_version(self, system_prompt_version: str) -> int:
        """Remove all semantic scopes populated under one prompt version."""
        scopes = [
            scope
            for scope, version in self.scope_versions.items()
            if version == system_prompt_version
        ]
        removed = sum(len(self.entries.get(scope, [])) for scope in scopes)
        for scope in scopes:
            self.entries.pop(scope, None)
            self.vectors.pop(scope, None)
            self.indexes.pop(scope, None)
            self.scope_versions.pop(scope, None)
        return removed


class ThreeTierCache:
    """Coordinate exact response, semantic response, and prefix caches."""

    def __init__(
        self,
        client: RedisClient,
        semantic_threshold: float,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Initialize all cache tiers with one policy threshold and TTL."""
        self.client = client
        self.semantic_threshold = semantic_threshold
        self.exact = ExactCache(client, ttl_seconds)
        self.semantic = SemanticCache(ttl_seconds)
        self.prefix = PrefixCache(client, ttl_seconds)

    def lookup(
        self,
        question: str,
        context: CacheContext,
        vector: NDArray[np.float32],
    ) -> CacheLookup:
        """Check exact, semantic, then static-prefix caches in order."""
        exact = self.exact.get(question, context)
        if exact is not None:
            return CacheLookup("exact", exact, 1.0)
        semantic = self.semantic.search(context, vector, self.semantic_threshold)
        if semantic is not None:
            value, similarity = semantic
            return CacheLookup("semantic", value, similarity)
        if self.prefix.contains(context):
            return CacheLookup("prefix", None, None)
        return CacheLookup("miss", None, None)

    def store_response(
        self,
        question: str,
        context: CacheContext,
        vector: NDArray[np.float32],
        value: CachedAnswer,
    ) -> None:
        """Populate exact, semantic, and prefix tiers after generation."""
        self.exact.set(question, context, value)
        self.semantic.add(question, context, vector, value)
        self.prefix.set(context)

    def invalidate_prompt_version(self, system_prompt_version: str) -> dict[str, int]:
        """Explicitly delete Redis and FAISS entries for one prompt version."""
        pattern = f"{CACHE_NAMESPACE}:*:{system_prompt_version}:*"
        redis_keys = list(self.client.scan_iter(match=pattern))
        redis_removed = self.client.delete(*redis_keys) if redis_keys else 0
        semantic_removed = self.semantic.invalidate_version(system_prompt_version)
        return {"redis_entries": redis_removed, "semantic_entries": semantic_removed}

    def reset_namespace(self) -> int:
        """Clear prior benchmark Redis entries without touching other applications."""
        keys = list(self.client.scan_iter(match=f"{CACHE_NAMESPACE}:*"))
        return self.client.delete(*keys) if keys else 0
