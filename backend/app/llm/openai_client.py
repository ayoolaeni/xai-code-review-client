"""Optional OpenAI provider (Section 8.9.1). Install with: pip install -e ".[openai]"."""

from __future__ import annotations

import time

from pydantic import BaseModel

from app.config import Settings
from app.llm.client import LLMError, LLMResult


class OpenAIClient:
    name = "openai"

    def __init__(self, settings: Settings):
        try:
            import openai
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                'LLM_PROVIDER=openai needs the openai package: pip install -e ".[openai]"'
            ) from e
        self._openai = openai
        self.model = settings.LLM_MODEL
        self._client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
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
        openai = self._openai
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": user}
        ]
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "timeout": timeout_s,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        start = time.monotonic()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.APITimeoutError as e:
            raise LLMError("timeout", "The AI service did not answer in time.") from e
        except openai.RateLimitError as e:
            raise LLMError("rate_limit", "The AI service is busy (rate limit).") from e
        except openai.AuthenticationError as e:
            raise LLMError("auth", "The AI service rejected the API key.") from e
        except openai.NotFoundError as e:
            raise LLMError("model_not_found", "The configured AI model was not found.") from e
        except openai.APIError as e:
            raise LLMError("api_error", "The AI service returned an error.") from e
        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        return LLMResult(
            text=choice.message.content or "",
            model=resp.model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=("MAX_TOKENS" if choice.finish_reason == "length" else choice.finish_reason),
        )
