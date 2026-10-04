"""Real Redis fixtures for durable workflow integration tests."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from redis import Redis

from src.store import RedisStore

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
def store() -> Iterator[RedisStore]:
    """Give each test a unique namespace and remove its keys afterward."""
    client = Redis.from_url(os.environ.get("REDIS_URL", DEFAULT_REDIS_URL), decode_responses=True)
    client.ping()
    result = RedisStore(client, f"test-{uuid4().hex}")
    yield result
    keys = list(client.scan_iter(match=f"wo04:{result.namespace}:*"))
    if keys:
        client.delete(*keys)
