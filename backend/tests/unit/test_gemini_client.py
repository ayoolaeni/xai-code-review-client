"""Gemini provider with a fake SDK client — never calls the network (Section 8.9.7)."""

import os
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.config import get_settings
from app.llm.client import LLMError
from app.llm.gemini_client import GeminiClient, map_api_error, parse_retry_delay
from app.llm.output_schema import ExplanationOutput
from app.llm.rate_limiter import RequestPacer


class FakeQuota:
    def __init__(self, limit=100):
        self.limit = limit
        self.used = 0
        self.exhausted = False
        self.tokens = []

    def check(self):
        if self.used >= self.limit:
            raise LLMError("quota_exhausted")

    def record(self, i=None, o=None):
        self.used += 1
        self.tokens.append((i, o))

    def exhaust_today(self):
        self.exhausted = True
        self.used = self.limit


def response(text='{"ok": true}', finish="STOP", block_reason=None, model="gemini-3-flash-001"):
    return SimpleNamespace(
        text=text,
        model_version=model,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
        prompt_feedback=(SimpleNamespace(block_reason=block_reason) if block_reason else None),
        usage_metadata=SimpleNamespace(
            prompt_token_count=100, candidates_token_count=50, thoughts_token_count=10
        ),
    )


def api_error(code, message="", status=None, details=None):
    body = {
        "error": {
            "code": code,
            "message": message,
            "status": status,
            "details": details or [],
        }
    }
    return errors.APIError(code, body)


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def get(self, model):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(outcomes, thinking="low"):
    settings = get_settings().model_copy(
        update={
            "GEMINI_API_KEY": "fake",
            "GEMINI_THINKING": thinking,
            "LLM_MODEL": "gemini-flash-latest",
        }
    )
    fake = SimpleNamespace(models=FakeModels(outcomes))
    quota = FakeQuota()
    client = GeminiClient(settings, sdk_client=fake, pacer=RequestPacer(1000), quota=quota)
    return client, fake.models, quota


def call(client, **kw):
    params = dict(
        temperature=0.2,
        max_output_tokens=8192,
        timeout_s=90,
        json_mode=True,
        response_model=ExplanationOutput,
    )
    params.update(kw)
    return client.complete("SYSTEM", "USER PROMPT", **params)


def test_request_parameters():
    client, models, quota = make_client([response()])
    result = call(client)
    cfg = models.calls[0].config
    assert models.calls[0].model == "gemini-flash-latest"
    assert models.calls[0].contents == "USER PROMPT"
    assert cfg.system_instruction == "SYSTEM"
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_json_schema == ExplanationOutput.model_json_schema()
    assert cfg.temperature == 0.2 and cfg.max_output_tokens == 8192
    assert cfg.thinking_config.thinking_level is not None
    assert result.model == "gemini-3-flash-001"  # resolved model name recorded
    assert result.input_tokens == 100 and result.output_tokens == 60
    assert quota.used == 1


def test_no_system_instruction_for_baseline():
    client, models, _ = make_client([response("plain text")])
    client.complete(
        None,
        "Explain this",
        temperature=0.2,
        max_output_tokens=100,
        timeout_s=10,
        json_mode=False,
    )
    cfg = models.calls[0].config
    assert (
        cfg.system_instruction is None and cfg.response_mime_type is None and cfg.response_json_schema is None
    )


def test_thinking_off_and_default():
    client, models, _ = make_client([response()], thinking="off")
    call(client)
    assert models.calls[0].config.thinking_config.thinking_budget == 0
    client, models, _ = make_client([response()], thinking="default")
    call(client)
    assert models.calls[0].config.thinking_config is None


def test_schema_rejected_retries_without_schema():
    client, models, _ = make_client(
        [
            api_error(
                400,
                "Invalid JSON payload: unknown name '$defs' in response_json_schema",
                "INVALID_ARGUMENT",
            ),
            response(),
        ]
    )
    call(client)
    assert models.calls[0].config.response_json_schema is not None
    assert models.calls[1].config.response_json_schema is None
    assert models.calls[1].config.response_mime_type == "application/json"
    models.outcomes.append(response())
    call(client)  # the schema stays disabled for later calls on the same client
    assert models.calls[2].config.response_json_schema is None


def test_thinking_rejected_steps_down():
    client, models, _ = make_client(
        [
            api_error(400, "thinking_level is not supported by this model", "INVALID_ARGUMENT"),
            response(),
        ]
    )
    call(client)
    assert models.calls[0].config.thinking_config.thinking_level is not None
    assert models.calls[1].config.thinking_config.thinking_budget == 1024


def test_empty_response_safety_is_blocked():
    client, _, _ = make_client([response(text=None, finish="SAFETY")])
    with pytest.raises(LLMError) as e:
        call(client)
    assert e.value.kind == "blocked"


def test_prompt_feedback_block_reason_is_blocked():
    client, _, _ = make_client([response(text="", finish="STOP", block_reason="PROHIBITED_CONTENT")])
    with pytest.raises(LLMError) as e:
        call(client)
    assert e.value.kind == "blocked"


def test_max_tokens_is_invalid_output_not_error():
    client, _, _ = make_client([response(text="", finish="MAX_TOKENS")])
    result = call(client)
    assert result.text == "" and result.finish_reason == "MAX_TOKENS"


@pytest.mark.parametrize(
    "error,kind",
    [
        (
            api_error(
                429,
                "Quota exceeded for metric: generate_content_free_tier_requests, limit: 10 per minute",
                "RESOURCE_EXHAUSTED",
                [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "17s",
                    },
                ],
            ),
            "rate_limit",
        ),
        (
            api_error(
                429,
                "Quota exceeded",
                "RESOURCE_EXHAUSTED",
                [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
                    }
                ],
            ),
            "quota_exhausted",
        ),
        (
            api_error(
                400,
                "API key not valid. Please pass a valid API key.",
                "INVALID_ARGUMENT",
                [{"reason": "API_KEY_INVALID"}],
            ),
            "auth",
        ),
        (api_error(401, "Unauthenticated", "UNAUTHENTICATED"), "auth"),
        (api_error(403, "Permission denied", "PERMISSION_DENIED"), "auth"),
        (
            api_error(404, "models/gemini-9 is not found", "NOT_FOUND"),
            "model_not_found",
        ),
        (api_error(500, "Internal error", "INTERNAL"), "api_error"),
        (api_error(503, "The model is overloaded", "UNAVAILABLE"), "api_error"),
        (TimeoutError("read timed out"), "timeout"),
        (ConnectionError("connection refused"), "api_error"),
    ],
)
def test_error_mapping(error, kind):
    client, _, quota = make_client([error])
    with pytest.raises(LLMError) as e:
        call(client)
    assert e.value.kind == kind
    assert quota.used >= 1  # failed calls also count
    if kind == "quota_exhausted":
        assert quota.exhausted
    if kind == "rate_limit":
        assert e.value.retry_after == 17


def test_retry_delay_parsing():
    assert parse_retry_delay({"error": {"details": [{"retryDelay": "17s"}]}}) == 17
    assert parse_retry_delay([{"retryDelay": "2.5s"}]) == 2.5
    assert parse_retry_delay({"error": {}}) is None
    assert map_api_error(429, "RESOURCE_EXHAUSTED", "daily limit reached", None).kind == "quota_exhausted"


def test_quota_checked_before_calling_api():
    client, models, quota = make_client([response()])
    quota.used = quota.limit
    with pytest.raises(LLMError) as e:
        call(client)
    assert e.value.kind == "quota_exhausted" and models.calls == []


def test_check_model_health():
    client, _, _ = make_client([SimpleNamespace(name="models/gemini-3-flash")])
    assert client.check_model() == "ok"
    client, _, _ = make_client([api_error(404, "not found", "NOT_FOUND")])
    assert client.check_model() == "model_not_found"


def test_check_model_transient_error_is_rechecked_sooner():
    client, _, _ = make_client([TimeoutError("read timed out")])
    assert client.check_model() == "api_error"
    client._health = (client._health[0] - 61, "api_error")  # 61 s later
    client._client.models.get = lambda model: SimpleNamespace(name="models/gemini-3-flash")
    assert client.check_model() == "ok"


@pytest.mark.live_gemini
@pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY_LIVE") and os.environ.get("RUN_LIVE_TESTS") == "1"),
    reason="set GEMINI_API_KEY_LIVE and RUN_LIVE_TESTS=1 to call the real Gemini API",
)
def test_live_gemini_analyses_p01(tmp_path):
    """Optional live test: analyses P01 with the real API and expects a completed AI report."""
    from app.db import Base, init_db
    from app.llm.client import set_client_override
    from app.pipeline.orchestrator import run_pipeline_for_code

    engine = init_db(f"sqlite:///{(tmp_path / 'live.db').as_posix()}")
    Base.metadata.create_all(engine)
    settings = get_settings().model_copy(
        update={
            "GEMINI_API_KEY": os.environ["GEMINI_API_KEY_LIVE"],
            "LLM_PROVIDER": "gemini",
        }
    )
    set_client_override(GeminiClient(settings))
    from tests.conftest import BENCHMARK_DIR

    code = (BENCHMARK_DIR / "samples" / "p01_user_lookup.py").read_text(encoding="utf-8")
    report = run_pipeline_for_code(code, "python")
    assert report["overview"]["ai_explanation_available"] is True
    assert any(f["cwe"] and f["cwe"]["id"] == "CWE-89" for f in report["findings"])
