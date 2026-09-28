"""Unit tests for cache isolation, tier order, TTL, and invalidation."""

from fnmatch import fnmatch
from pathlib import Path
import sys

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cache import SemanticCache, ThreeTierCache, answer_scope_key
from src.models import CacheContext, CachedAnswer


class FakeRedis:
    """Small in-memory implementation of the Redis operations under test."""

    def __init__(self) -> None:
        """Initialize an empty key-value store."""
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        """Return one stored string."""
        return self.values.get(key)

    def setex(self, key: str, _ttl_seconds: int, value: str) -> bool:
        """Store a string while accepting the production TTL argument."""
        self.values[key] = value
        return True

    def scan_iter(self, match: str) -> list[str]:
        """Return keys matching the requested Redis-style glob."""
        return [key for key in self.values if fnmatch(key, match)]

    def delete(self, *keys: bytes | str) -> int:
        """Delete keys and return the number that existed."""
        removed = 0
        for raw_key in keys:
            key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else raw_key
            removed += int(self.values.pop(key, None) is not None)
        return removed


def _context(version: str = "v1", tenant: str = "tenant-a") -> CacheContext:
    """Build an isolated cache context for tests."""
    return CacheContext(
        model="model-a",
        temperature=0.0,
        tools=("search",),
        system_prompt_version=version,
        tenant_id=tenant,
        customer_tier="standard",
    )


def _vector(first: float, second: float) -> NDArray[np.float32]:
    """Build a small float32 embedding."""
    return np.asarray([first, second], dtype=np.float32)


def test_answer_scope_isolates_tenant_and_prompt_version() -> None:
    """Changing tenant or prompt version must produce a different response scope."""
    base = answer_scope_key(_context())
    assert base != answer_scope_key(_context(tenant="tenant-b"))
    assert base != answer_scope_key(_context(version="v2"))


def test_three_tiers_and_prompt_bust() -> None:
    """Exact reuse should win, while a new prompt version should miss all tiers."""
    cache = ThreeTierCache(FakeRedis(), semantic_threshold=0.95)
    question = "How do I reset my password?"
    vector = _vector(1.0, 0.0)
    assert cache.lookup(question, _context(), vector).level == "miss"
    cache.store_response(
        question, _context(), vector, CachedAnswer("Use the reset link.", "reset")
    )
    assert cache.lookup("  HOW do I reset my password? ", _context(), vector).level == "exact"
    assert cache.lookup(question, _context(version="v2"), vector).level == "miss"
    removed = cache.invalidate_prompt_version("v1")
    assert removed == {"redis_entries": 2, "semantic_entries": 1}


def test_semantic_cache_applies_threshold_and_ttl() -> None:
    """Semantic entries must satisfy both similarity and expiration checks."""
    cache = SemanticCache(ttl_seconds=10)
    cache.add(
        "seed",
        _context(),
        _vector(1.0, 0.0),
        CachedAnswer("answer", "intent"),
        now=100.0,
    )
    assert cache.search(_context(), _vector(0.99, 0.01), 0.95, now=105.0) is not None
    assert cache.search(_context(), _vector(0.0, 1.0), 0.95, now=105.0) is None
    assert cache.search(_context(), _vector(1.0, 0.0), 0.95, now=111.0) is None
