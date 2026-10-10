"""LLM client interface, error type and the provider factory (Section 8.9, NFR9)."""

from __future__ import annotations

import threading
from typing import Protocol

from pydantic import BaseModel

from app.config import Settings, get_settings

ERROR_KINDS = (
    "timeout",
    "rate_limit",
    "quota_exhausted",
    "blocked",
    "api_error",
    "auth",
    "model_not_found",
)
RETRYABLE_KINDS = {"rate_limit", "timeout", "api_error", "blocked"}


class LLMResult(BaseModel):
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    finish_reason: str | None = None  # e.g. "MAX_TOKENS" (Gemini); used by the repair loop


class LLMError(Exception):
    def __init__(self, kind: str, message: str = "", retry_after: float | None = None):
        if kind not in ERROR_KINDS:
            raise ValueError(f"unknown LLMError kind {kind!r}")
        super().__init__(message or kind)
        self.kind = kind
        self.message = message or kind
        self.retry_after = retry_after


class LLMClient(Protocol):
    name: str  # "gemini" | "mock" | "openai" | "anthropic"
    model: str

    def complete(
        self,
        system: str | None,
        user: str,
        *,
        temperature: float,
        max_output_tokens: int,
        timeout_s: int,
        json_mode: bool,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        # response_model: the Pydantic model the reply must match (ExplanationOutput or RiskOnlyOutput).
        # Providers that support native structured output (Gemini) pass it to the API; others ignore it.
        ...


class NotConfiguredClient:
    """Used when the selected provider has no API key: every call fails with `auth`."""

    def __init__(self, provider: str, model: str):
        self.name = provider
        self.model = model

    def complete(self, system, user, **_kwargs) -> LLMResult:
        raise LLMError("auth", "The AI service is not configured.")


_lock = threading.Lock()
_override: LLMClient | None = None
_cached: tuple[str, LLMClient] | None = None


def set_client_override(client: LLMClient | None) -> None:
    """Tests and scripts can force a specific client (e.g. FailingMockClient)."""
    global _override
    with _lock:
        _override = client


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Factory — the ONLY place where providers are chosen."""
    global _cached
    settings = settings or get_settings()
    with _lock:
        if _override is not None:
            return _override
        key = f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}:{bool(settings.llm_api_key)}"
        if _cached and _cached[0] == key:
            return _cached[1]
        client = _build(settings)
        _cached = (key, client)
        return client


def _build(settings: Settings) -> LLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        from app.llm.mock_client import MockClient

        return MockClient()
    if not settings.llm_api_key:
        return NotConfiguredClient(provider, settings.LLM_MODEL)
    if provider == "gemini":
        from app.llm.gemini_client import GeminiClient

        return GeminiClient(settings)
    if provider == "openai":
        from app.llm.openai_client import OpenAIClient

        return OpenAIClient(settings)
    if provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient

        return AnthropicClient(settings)
    raise ValueError(f"Unknown LLM_PROVIDER {provider!r}")
