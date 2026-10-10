"""Google Gemini provider — the project's chosen LLM (Section 8.9.5).

Uses the current Google Gen AI SDK (`google-genai`). Every real API call goes through the free-tier
daily quota check and the per-minute pacer (Section 8.9.6).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time

from pydantic import BaseModel

from app.config import Settings
from app.llm.client import LLMError, LLMResult
from app.llm.rate_limiter import DailyQuota, RequestPacer, get_pacer, get_quota

log = logging.getLogger(__name__)

HEALTH_TTL_SECONDS = 600
HEALTH_ERROR_TTL_SECONDS = 60  # transient errors (network, timeouts) are re-checked sooner
BLOCK_REASONS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}
_RETRY_DELAY_RE = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')
_DAILY_RE = re.compile(r"PerDay|per[ _-]day|daily", re.IGNORECASE)

_sdk_lock = threading.Lock()
_sdk_clients: dict[tuple[str, int], object] = {}


def _make_sdk_client(api_key: str, timeout_s: int):
    """Created once per (key, timeout) and reused (module-level singleton)."""
    from google import genai
    from google.genai import types

    key = (api_key, timeout_s)
    with _sdk_lock:
        if key not in _sdk_clients:
            _sdk_clients[key] = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=timeout_s * 1000,  # milliseconds
                    retry_options=types.HttpRetryOptions(attempts=1),  # our own retry policy (8.9.3)
                ),
            )
        return _sdk_clients[key]


def parse_retry_delay(details: object) -> float | None:
    """Gemini puts google.rpc.RetryInfo.retryDelay (e.g. "17s") in the 429 error details."""
    try:
        text = json.dumps(details) if not isinstance(details, str) else details
    except (TypeError, ValueError):
        text = str(details)
    m = _RETRY_DELAY_RE.search(text)
    return float(m.group(1)) if m else None


def map_api_error(code: int | None, status: str | None, message: str | None, details: object) -> LLMError:
    """Map a google.genai APIError to an LLMError kind (table in 8.9.5)."""
    status = (status or "").upper()
    text = f"{message or ''} {json.dumps(details, default=str) if details is not None else ''}"
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        if _DAILY_RE.search(text):
            return LLMError("quota_exhausted", "The free AI quota for today has been used up.")
        delay = parse_retry_delay(details)
        return LLMError("rate_limit", "The AI service is busy (rate limit).", retry_after=delay)
    if code in (401, 403) or status in ("UNAUTHENTICATED", "PERMISSION_DENIED") or "API_KEY_INVALID" in text:
        return LLMError("auth", "The AI service rejected the API key.")
    if code == 404 or status == "NOT_FOUND":
        return LLMError("model_not_found", "The configured AI model was not found for this API key.")
    if code == 504 or status == "DEADLINE_EXCEEDED":
        return LLMError("timeout", "The AI service timed out.")
    return LLMError("api_error", f"The AI service returned an error ({code} {status}).".strip())


def _is_schema_rejection(message: str) -> bool:
    m = message.lower()
    return any(
        s in m
        for s in (
            "schema",
            "response_json_schema",
            "responsejsonschema",
            "unknown name",
            "$ref",
            "$defs",
        )
    )


def _is_thinking_rejection(message: str) -> bool:
    m = message.lower()
    return "thinking" in m


class GeminiClient:
    name = "gemini"

    def __init__(
        self,
        settings: Settings,
        sdk_client: object | None = None,
        pacer: RequestPacer | None = None,
        quota: DailyQuota | None = None,
    ):
        self.model = settings.LLM_MODEL
        self.settings = settings
        self._client = sdk_client or _make_sdk_client(settings.GEMINI_API_KEY, settings.LLM_TIMEOUT_SECONDS)
        self._pacer = pacer
        self._quota = quota
        self._schema_supported = True
        self._schema_warned = False
        # Thinking configurations to try in order; the first one the model accepts is remembered.
        self._thinking_options = self._thinking_candidates(settings.GEMINI_THINKING)
        self._thinking_index = 0
        self.resolved_model: str | None = None
        self._health: tuple[float, str] | None = None

    # ---------- helpers ----------
    @property
    def pacer(self) -> RequestPacer:
        return self._pacer or get_pacer()

    @property
    def quota(self) -> DailyQuota:
        return self._quota or get_quota()

    @staticmethod
    def _thinking_candidates(mode: str) -> list[dict | None]:
        if mode == "default":
            return [None]
        if mode == "off":
            # budget 0 where the model allows it (2.5 Flash), otherwise the lowest level.
            return [
                {"thinking_budget": 0},
                {"thinking_level": "minimal"},
                {"thinking_level": "low"},
                None,
            ]
        # "low": Gemini 3 models take a level; 2.5 models take a small token budget.
        return [{"thinking_level": "low"}, {"thinking_budget": 1024}, None]

    def _build_config(
        self,
        system: str | None,
        temperature: float,
        max_output_tokens: int,
        json_mode: bool,
        response_model: type[BaseModel] | None,
    ):
        from google.genai import types

        kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if system:
            kwargs["system_instruction"] = system
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        if response_model is not None and self._schema_supported:
            kwargs["response_json_schema"] = response_model.model_json_schema()
        thinking = self._thinking_options[self._thinking_index]
        if thinking:
            kwargs["thinking_config"] = types.ThinkingConfig(**thinking)
        return types.GenerateContentConfig(**kwargs)

    def _raw_call(self, user: str, config):
        """One real API request: quota check → pacer → request → usage bookkeeping."""
        from google.genai import errors

        quota = self.quota
        quota.check()
        self.pacer.acquire()
        try:
            response = self._client.models.generate_content(model=self.model, contents=user, config=config)
        except errors.APIError as e:
            quota.record()
            err = map_api_error(
                getattr(e, "code", None),
                getattr(e, "status", None),
                getattr(e, "message", None),
                getattr(e, "details", None),
            )
            if err.kind == "quota_exhausted":
                quota.exhaust_today()
            err.raw_message = str(getattr(e, "message", "") or "")  # type: ignore[attr-defined]
            raise err from e
        except Exception as e:  # network problems and client-side timeouts
            quota.record()
            name = type(e).__name__.lower()
            if "timeout" in name or isinstance(e, TimeoutError):
                raise LLMError("timeout", "The AI service did not answer in time.") from e
            raise LLMError("api_error", f"Could not reach the AI service ({type(e).__name__}).") from e
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", None) if usage else None
        out_tok = None
        if usage:
            out_tok = (getattr(usage, "candidates_token_count", 0) or 0) + (
                getattr(usage, "thoughts_token_count", 0) or 0
            )
        quota.record(in_tok, out_tok)
        return response, in_tok, out_tok

    # ---------- public API ----------
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
        start = time.monotonic()
        while True:
            config = self._build_config(system, temperature, max_output_tokens, json_mode, response_model)
            try:
                response, in_tok, out_tok = self._raw_call(user, config)
                break
            except LLMError as e:
                raw = getattr(e, "raw_message", "")
                if e.kind == "api_error" and raw:
                    if response_model is not None and self._schema_supported and _is_schema_rejection(raw):
                        self._schema_supported = False
                        if not self._schema_warned:
                            log.warning(
                                "Gemini rejected the response schema; continuing without it: %s",
                                raw[:200],
                            )
                            self._schema_warned = True
                        continue
                    if _is_thinking_rejection(raw) and self._thinking_index < len(self._thinking_options) - 1:
                        log.warning(
                            "Gemini rejected thinking config %s; trying the next option",
                            self._thinking_options[self._thinking_index],
                        )
                        self._thinking_index += 1
                        continue
                raise

        latency_ms = int((time.monotonic() - start) * 1000)
        model_name = getattr(response, "model_version", None) or self.model
        self.resolved_model = model_name

        text = None
        try:
            text = response.text
        except Exception:  # noqa: BLE001 - .text raises in some SDK versions when there are no parts
            text = None
        finish = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            fr = getattr(candidates[0], "finish_reason", None)
            finish = getattr(fr, "name", None) or (str(fr) if fr is not None else None)
            if finish and "." in finish:
                finish = finish.rsplit(".", 1)[-1]
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            block_reason = getattr(feedback, "block_reason", None) if feedback else None
            if block_reason or (finish in BLOCK_REASONS):
                raise LLMError("blocked", "The AI service declined to analyse this code.")
            if finish == "RECITATION":
                raise LLMError("blocked", "The AI service stopped its answer (recitation check).")
            if finish == "MAX_TOKENS":
                # Treated as invalid output: the repair loop asks for a shorter reply.
                return LLMResult(
                    text="",
                    model=model_name,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=latency_ms,
                    finish_reason="MAX_TOKENS",
                )
            raise LLMError("api_error", "The AI service returned an empty answer.")
        return LLMResult(
            text=text,
            model=model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            finish_reason=finish,
        )

    def check_model(self) -> str:
        """Health check (cached 10 minutes): ok | model_not_found | auth | api_error."""
        now = time.monotonic()
        if self._health:
            ttl = HEALTH_ERROR_TTL_SECONDS if self._health[1] == "api_error" else HEALTH_TTL_SECONDS
            if now - self._health[0] < ttl:
                return self._health[1]
        from google.genai import errors

        status = "ok"
        try:
            info = self._client.models.get(model=self.model)
            self.resolved_model = getattr(info, "name", None) or self.resolved_model
        except errors.APIError as e:
            kind = map_api_error(
                getattr(e, "code", None),
                getattr(e, "status", None),
                getattr(e, "message", None),
                getattr(e, "details", None),
            ).kind
            status = {"model_not_found": "model_not_found", "auth": "auth"}.get(kind, "api_error")
            if status == "model_not_found":
                log.error(
                    "Gemini model '%s' was not found for this API key. Set LLM_MODEL to a current free-tier "
                    "Flash model listed in Google AI Studio.",
                    self.model,
                )
            elif status == "api_error":
                log.warning("Gemini health check failed: %s %s", getattr(e, "code", None), type(e).__name__)
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini health check failed (network or timeout): %s", type(e).__name__)
            status = "api_error"
        self._health = (now, status)
        return status
