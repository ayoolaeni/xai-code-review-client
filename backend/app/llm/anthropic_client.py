"""Optional Anthropic provider (Section 8.9.2). Install with: pip install -e ".[anthropic]"."""

from __future__ import annotations

import time

from pydantic import BaseModel

from app.config import Settings
from app.llm.client import LLMError, LLMResult


class AnthropicClient:
    name = "anthropic"

    def __init__(self, settings: Settings):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                'LLM_PROVIDER=anthropic needs the anthropic package: pip install -e ".[anthropic]"'
            ) from e
        self._anthropic = anthropic
        self.model = settings.LLM_MODEL
        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )

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
        anthropic = self._anthropic
        content = user + ("\n\nReply with the JSON object only." if json_mode else "")
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": content}],
            "timeout": timeout_s,
        }
        if system:
            kwargs["system"] = system
        start = time.monotonic()
        try:
            resp = self._client.messages.create(**kwargs)
        except anthropic.APITimeoutError as e:
            raise LLMError("timeout", "The AI service did not answer in time.") from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate_limit", "The AI service is busy (rate limit).") from e
        except anthropic.AuthenticationError as e:
            raise LLMError("auth", "The AI service rejected the API key.") from e
        except anthropic.NotFoundError as e:
            raise LLMError("model_not_found", "The configured AI model was not found.") from e
        except anthropic.APIError as e:
            raise LLMError("api_error", "The AI service returned an error.") from e
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        return LLMResult(
            text=text,
            model=resp.model,
            input_tokens=getattr(resp.usage, "input_tokens", None),
            output_tokens=getattr(resp.usage, "output_tokens", None),
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=("MAX_TOKENS" if resp.stop_reason == "max_tokens" else resp.stop_reason),
        )
