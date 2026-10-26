"""Small async OpenAI-compatible client with bounded retries and no key logging."""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from typing import Any

import httpx


REQUEST_TIMEOUT_SECONDS = 90.0
MAX_ATTEMPTS = 5
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
BASE_BACKOFF_SECONDS = 1.0


@dataclass(frozen=True)
class LLMSettings:
    """Runtime endpoint settings loaded only from environment variables."""

    provider: str
    base_url: str
    api_key: str
    model: str
    judge_model: str
    concurrency: int
    max_tokens: int

    @classmethod
    def from_environment(cls) -> LLMSettings:
        """Read local Compose-injected settings and validate required model fields."""
        provider = os.getenv("LLM_PROVIDER", "openai-compatible").strip().lower()
        default_url = "https://api.anthropic.com/v1" if provider == "anthropic" else "https://api.openai.com/v1"
        base_url = os.getenv("LLM_BASE_URL", default_url).strip().rstrip("/") or default_url
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        judge_model = os.getenv("JUDGE_MODEL", "").strip() or model
        concurrency = int(os.getenv("LLM_CONCURRENCY", "4"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "96"))
        if not api_key or not model:
            raise ValueError(
                "Set LLM_API_KEY and LLM_MODEL in the local .env file; do not commit secrets"
            )
        if concurrency < 1 or max_tokens < 1:
            raise ValueError("LLM_CONCURRENCY and LLM_MAX_TOKENS must be positive")
        if provider not in {"openai-compatible", "anthropic"}:
            raise ValueError("LLM_PROVIDER must be openai-compatible or anthropic")
        return cls(provider, base_url, api_key, model, judge_model, concurrency, max_tokens)


@dataclass(frozen=True)
class Completion:
    """Model text and optional provider-reported token counts."""

    text: str
    prompt_tokens: int | None
    completion_tokens: int | None


class LLMClient:
    """Call a configured OpenAI-compatible or Anthropic endpoint."""

    def __init__(self, settings: LLMSettings, client: httpx.AsyncClient) -> None:
        """Keep a shared HTTP client for connection pooling across calls."""
        self.settings = settings
        self.client = client

    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> Completion:
        """Request one deterministic completion and retry only transient errors."""
        request_body: dict[str, Any]
        if self.settings.provider == "anthropic":
            url = f"{self.settings.base_url}/messages"
            headers = {
                "x-api-key": self.settings.api_key,
                "anthropic-version": "2023-06-01",
            }
            request_body = {
                "model": model or self.settings.model,
                "temperature": 0,
                "max_tokens": self.settings.max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        else:
            url = f"{self.settings.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {self.settings.api_key}"}
            request_body = {
                "model": model or self.settings.model,
                "temperature": 0,
                "max_tokens": self.settings.max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self.client.post(url, headers=headers, json=request_body)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                response.raise_for_status()
                payload = response.json()
                if self.settings.provider == "anthropic":
                    text = "".join(
                        str(item.get("text", ""))
                        for item in payload.get("content", [])
                        if item.get("type") == "text"
                    )
                    prompt_tokens = payload.get("usage", {}).get("input_tokens")
                    completion_tokens = payload.get("usage", {}).get("output_tokens")
                else:
                    text = payload["choices"][0]["message"]["content"]
                    prompt_tokens = payload.get("usage", {}).get("prompt_tokens")
                    completion_tokens = payload.get("usage", {}).get("completion_tokens")
                if isinstance(text, list):
                    text = "".join(
                        str(item.get("text", "")) for item in text if isinstance(item, dict)
                    )
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Provider returned empty assistant content")
                return Completion(
                    text=text.strip(),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in RETRYABLE_STATUS_CODES or attempt + 1 == MAX_ATTEMPTS:
                    raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt + 1 == MAX_ATTEMPTS:
                    raise
            delay = BASE_BACKOFF_SECONDS * (2**attempt) + random.random()
            await asyncio.sleep(delay)
        raise RuntimeError("Completion retry loop ended unexpectedly")


def new_http_client() -> httpx.AsyncClient:
    """Create a connection-pooled async client with a bounded request timeout."""
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
