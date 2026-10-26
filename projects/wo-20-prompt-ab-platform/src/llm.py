"""Small async OpenAI-compatible client with bounded retries and no key logging."""

from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


REQUEST_TIMEOUT_SECONDS = 90.0
MAX_ATTEMPTS = 5
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
BASE_BACKOFF_SECONDS = 1.0
SUPPORTED_BUDGET_MODEL = "gpt-6-luna"
INPUT_USD_PER_MILLION = 0.10
OUTPUT_USD_PER_MILLION = 0.50
REQUEST_OVERHEAD_BYTES = 512


class BudgetExceededError(RuntimeError):
    """Raised before sending an API request that would exceed the local cost cap."""


class CostBudget:
    """Persist conservative worst-case request reservations across resumed runs."""

    def __init__(self, path: Path, model: str, limit_usd: float) -> None:
        """Load an existing reservation ledger or initialize a new one."""
        if model != SUPPORTED_BUDGET_MODEL:
            raise ValueError(f"Cost guard pricing is verified only for {SUPPORTED_BUDGET_MODEL}")
        if limit_usd <= 0:
            raise ValueError("COST_LIMIT_USD must be positive")
        self.path = path
        self.model = model
        self.limit_usd = limit_usd
        self._lock = asyncio.Lock()
        self._reserved_usd = 0.0
        if path.exists():
            ledger = json.loads(path.read_text(encoding="utf-8"))
            if ledger.get("model") != model:
                raise ValueError("Budget ledger model differs; do not reuse it for another model")
            self._reserved_usd = float(ledger.get("reserved_usd", 0.0))
            if self._reserved_usd > limit_usd:
                raise BudgetExceededError("Existing reservations already exceed COST_LIMIT_USD")

    @property
    def reserved_usd(self) -> float:
        """Return the conservative total reserved request cost."""
        return self._reserved_usd

    async def reserve(self, system: str, user: str, max_tokens: int) -> float:
        """Reserve a byte-count upper bound for one attempt before its network call."""
        input_token_upper_bound = (
            len(system.encode("utf-8"))
            + len(user.encode("utf-8"))
            + REQUEST_OVERHEAD_BYTES
        )
        request_cost_upper_bound = (
            input_token_upper_bound * INPUT_USD_PER_MILLION
            + max_tokens * OUTPUT_USD_PER_MILLION
        ) / 1_000_000
        async with self._lock:
            projected = self._reserved_usd + request_cost_upper_bound
            if projected > self.limit_usd:
                raise BudgetExceededError(
                    f"Request blocked: conservative reservation would reach ${projected:.4f}, "
                    f"above local cap ${self.limit_usd:.2f}"
                )
            self._reserved_usd = projected
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps({
                "model": self.model,
                "reserved_usd": round(self._reserved_usd, 8),
                "limit_usd": self.limit_usd,
                "reservation_basis": "UTF-8 byte upper bound + max output tokens per API attempt",
            }, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        return request_cost_upper_bound


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
    cost_limit_usd: float = 8.0

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
        cost_limit_usd = float(os.getenv("COST_LIMIT_USD", "8"))
        if not api_key or not model:
            raise ValueError(
                "Set LLM_API_KEY and LLM_MODEL in the local .env file; do not commit secrets"
            )
        if concurrency < 1 or max_tokens < 1 or cost_limit_usd <= 0:
            raise ValueError("Concurrency, output tokens, and cost limit must be positive")
        if provider not in {"openai-compatible", "anthropic"}:
            raise ValueError("LLM_PROVIDER must be openai-compatible or anthropic")
        if provider != "openai-compatible":
            raise ValueError("The verified cost cap currently supports OpenAI-compatible endpoints")
        if model != SUPPORTED_BUDGET_MODEL or judge_model != SUPPORTED_BUDGET_MODEL:
            raise ValueError(
                f"Set LLM_MODEL and JUDGE_MODEL to {SUPPORTED_BUDGET_MODEL}; "
                "the local spend guard is priced for this model"
            )
        return cls(
            provider, base_url, api_key, model, judge_model, concurrency,
            max_tokens, cost_limit_usd,
        )


@dataclass(frozen=True)
class Completion:
    """Model text and optional provider-reported token counts."""

    text: str
    prompt_tokens: int | None
    completion_tokens: int | None


class LLMClient:
    """Call a configured OpenAI-compatible or Anthropic endpoint."""

    def __init__(
        self,
        settings: LLMSettings,
        client: httpx.AsyncClient,
        cost_budget: CostBudget | None = None,
    ) -> None:
        """Keep a shared HTTP client for connection pooling across calls."""
        self.settings = settings
        self.client = client
        self.cost_budget = cost_budget

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
                "max_completion_tokens": self.settings.max_tokens,
                "reasoning_effort": "none",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        for attempt in range(MAX_ATTEMPTS):
            try:
                if self.cost_budget is not None:
                    await self.cost_budget.reserve(system, user, self.settings.max_tokens)
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
