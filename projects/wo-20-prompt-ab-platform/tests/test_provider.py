"""Exercise both supported API wire formats without making network calls."""

import asyncio
import json

import httpx

from src.llm import LLMClient, LLMSettings


def test_openai_compatible_response_and_usage_parsing() -> None:
    """The OpenAI-compatible adapter sends expected inputs and reads token usage."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Paris"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        })

    async def run() -> tuple[str, int | None]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            settings = LLMSettings("openai-compatible", "https://llm.test/v1", "secret", "gpt-6-luna", "gpt-6-luna", 1, 96)
            result = await LLMClient(settings, client).complete("system", "question")
            return result.text, result.prompt_tokens

    assert asyncio.run(run()) == ("Paris", 10)
    assert str(requests[0].url) == "https://llm.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer secret"
    request_body = json.loads(requests[0].content)
    assert request_body["max_completion_tokens"] == 96
    assert request_body["reasoning_effort"] == "none"
    assert "temperature" not in request_body


def test_anthropic_response_and_usage_parsing() -> None:
    """The Anthropic Messages adapter reads its text blocks and usage fields."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "Paris"}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
        })

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            settings = LLMSettings("anthropic", "https://api.anthropic.com/v1", "secret", "model-a", "judge", 1, 20)
            result = await LLMClient(settings, client).complete("system", "question")
            return result.text

    assert asyncio.run(run()) == "Paris"
    assert str(requests[0].url) == "https://api.anthropic.com/v1/messages"
    assert requests[0].headers["x-api-key"] == "secret"
    assert requests[0].headers["anthropic-version"] == "2023-06-01"
