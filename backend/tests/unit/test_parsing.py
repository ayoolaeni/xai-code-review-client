"""LLM reply parsing, semantic checks and the repair loop (Sections 8.8 and 8.10)."""

import json

import pytest

from app.llm import parsing
from app.llm.client import LLMError, LLMResult
from app.llm.output_schema import ExplanationOutput, RiskOnlyOutput

CODE = "import os\n\ndef f(x):\n    return os.system(x)\n\nprint(f('ls'))"


def valid_explanation(**overrides) -> dict:
    data = {
        "purpose_summary": "Runs a shell command given by the caller.",
        "breakdown": [
            {
                "start_line": 1,
                "end_line": 2,
                "title": "Imports",
                "explanation": "Imports os.",
            },
            {
                "start_line": 3,
                "end_line": 4,
                "title": "f",
                "explanation": "Runs a command.",
            },
            {
                "start_line": 5,
                "end_line": 6,
                "title": "Top level",
                "explanation": "Calls f.",
            },
        ],
        "findings": [
            {
                "title": "Command injection",
                "category": "security",
                "start_line": 4,
                "end_line": 4,
                "description": "Input reaches a shell.",
                "evidence": "os.system(x)",
                "recommendation": "Use subprocess with a list.",
                "severity_suggested": "CRITICAL",
                "cwe_id": "cwe-78",
                "model_uncertain": False,
                "related_static_ids": ["S1", "S99"],
            }
        ],
        "static_assessment": [{"static_id": "S1", "verdict": "agree", "reason": "Real."}],
        "improved_code": "import subprocess\n\ndef f(x):\n    return subprocess.run([x]).returncode\n\nprint(f('ls'))",
        "changes": [
            {
                "number": 1,
                "description": "Use subprocess.",
                "reason": "No shell.",
                "related_findings": [1],
                "original_lines": [4, 4],
            }
        ],
        "sensitive_domains": [],
        "limitations": ["Callers unknown."],
    }
    data.update(overrides)
    return data


CHECK = parsing.explanation_checker(CODE, ["S1"])


# ---------- text handling ----------
def test_strip_code_fence():
    assert parsing.strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert parsing.strip_fences('{"a": 1}') == '{"a": 1}'


def test_extract_first_balanced_object_respecting_strings():
    text = 'Here you go: {"a": "brace } inside", "b": {"c": 2}} trailing {"x": 1}'
    assert json.loads(parsing.extract_json_object(text)) == {
        "a": "brace } inside",
        "b": {"c": 2},
    }
    assert parsing.extract_json_object("no json here") is None


def test_parse_valid_reply_with_prose_and_fence():
    reply = "Sure!\n```json\n" + json.dumps(valid_explanation()) + "\n```"
    value, errors = parsing.parse_reply(reply, ExplanationOutput, CHECK, False)
    assert errors == [] and value is not None
    assert value.findings[0].cwe_id == "CWE-78"  # normalised
    assert value.findings[0].related_static_ids == ["S1"]  # unknown S99 dropped


def test_schema_errors_are_listed():
    bad = valid_explanation(breakdown=[], purpose_summary="short")
    value, errors = parsing.parse_reply(json.dumps(bad), ExplanationOutput, CHECK, False)
    assert value is None
    assert any("breakdown" in e for e in errors) and any("purpose_summary" in e for e in errors)


def test_invalid_json_error():
    value, errors = parsing.parse_reply("{not json", ExplanationOutput, CHECK, False)
    assert value is None and errors


# ---------- semantic checks ----------
def test_overlapping_sections_rejected():
    data = valid_explanation(
        breakdown=[
            {"start_line": 1, "end_line": 4, "title": "A", "explanation": "x"},
            {"start_line": 3, "end_line": 6, "title": "B", "explanation": "y"},
        ]
    )
    value, errors = parsing.parse_reply(json.dumps(data), ExplanationOutput, CHECK, False)
    assert value is None and any("overlap" in e for e in errors)


def test_low_coverage_rejected():
    data = valid_explanation(breakdown=[{"start_line": 1, "end_line": 2, "title": "A", "explanation": "x"}])
    value, errors = parsing.parse_reply(json.dumps(data), ExplanationOutput, CHECK, False)
    assert value is None and any("covers only" in e for e in errors)


def test_end_before_start_rejected():
    f = valid_explanation()["findings"][0] | {"start_line": 4, "end_line": 2}
    value, errors = parsing.parse_reply(
        json.dumps(valid_explanation(findings=[f])), ExplanationOutput, CHECK, False
    )
    assert value is None and any("before start_line" in e for e in errors)


def test_finding_slightly_outside_is_clamped():
    f = valid_explanation()["findings"][0] | {"start_line": 6, "end_line": 8}
    value, errors = parsing.parse_reply(
        json.dumps(valid_explanation(findings=[f])), ExplanationOutput, CHECK, False
    )
    assert errors == [] and (
        value.findings[0].start_line,
        value.findings[0].end_line,
    ) == (6, 6)


def test_finding_far_outside_rejected():
    f = valid_explanation()["findings"][0] | {"start_line": 40, "end_line": 41}
    value, errors = parsing.parse_reply(
        json.dumps(valid_explanation(findings=[f])), ExplanationOutput, CHECK, False
    )
    assert value is None and any("outside the code" in e for e in errors)


def test_missing_static_assessment_is_error_then_allowed_on_final_attempt():
    data = json.dumps(valid_explanation(static_assessment=[]))
    value, errors = parsing.parse_reply(data, ExplanationOutput, CHECK, False)
    assert value is None and any("S1" in e for e in errors)
    value, errors = parsing.parse_reply(data, ExplanationOutput, CHECK, True)
    assert errors == [] and value.static_assessment == []


def test_bad_related_findings():
    change = valid_explanation()["changes"][0] | {"related_findings": [1, 7]}
    data = json.dumps(valid_explanation(changes=[change]))
    value, errors = parsing.parse_reply(data, ExplanationOutput, CHECK, False)
    assert value is None and any("related_findings" in e for e in errors)
    value, errors = parsing.parse_reply(data, ExplanationOutput, CHECK, True)
    assert errors == [] and value.changes[0].related_findings == [1]


def test_improved_code_must_differ_when_findings_exist():
    data = json.dumps(valid_explanation(improved_code=CODE))
    value, errors = parsing.parse_reply(data, ExplanationOutput, CHECK, False)
    assert value is None and any("identical" in e for e in errors)


def test_risks_checker():
    check = parsing.risks_checker(CODE)
    data = {
        "findings": [
            {
                "title": "x",
                "category": "security",
                "start_line": 4,
                "end_line": 4,
                "severity_suggested": "HIGH",
                "cwe_id": "78",
            }
        ]
    }
    value, errors = parsing.parse_reply(json.dumps(data), RiskOnlyOutput, check, False)
    assert errors == [] and value.findings[0].cwe_id == "CWE-78"


# ---------- the request / repair loop ----------
class ScriptedClient:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, system, user, **kwargs):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, LLMResult):
            return reply
        return LLMResult(text=reply, model=self.model, latency_ms=5)


def _run(client, **kw):
    return parsing.call_with_repair(
        client, "system", "ORIGINAL PROMPT", ExplanationOutput, CHECK, temperature=0.2, max_retries=2, **kw
    )


def test_valid_first_time():
    out = _run(ScriptedClient([json.dumps(valid_explanation())]))
    assert out.ok and out.attempts == 1


def test_repair_after_invalid_output():
    client = ScriptedClient(["not json", json.dumps(valid_explanation())])
    out = _run(client)
    assert out.ok and out.attempts == 2
    assert "Your previous reply could not be used" in client.prompts[1]
    assert "not json" in client.prompts[1]


def test_gives_up_after_budget():
    out = _run(ScriptedClient(["nope", "nope", "nope"]))
    assert not out.ok and out.attempts == 3 and out.error_kind == "invalid_output"


def test_retryable_errors_retry_with_same_prompt():
    client = ScriptedClient([LLMError("rate_limit", retry_after=5), json.dumps(valid_explanation())])
    out = _run(client)
    assert out.ok and out.attempts == 2 and client.prompts == ["ORIGINAL PROMPT", "ORIGINAL PROMPT"]


@pytest.mark.parametrize("kind", ["auth", "model_not_found", "quota_exhausted"])
def test_non_retryable_errors_stop_immediately(kind):
    client = ScriptedClient([LLMError(kind), json.dumps(valid_explanation())])
    out = _run(client)
    assert not out.ok and out.attempts == 1 and out.error_kind == kind


def test_blocked_retried_once_only():
    client = ScriptedClient([LLMError("blocked"), LLMError("blocked"), json.dumps(valid_explanation())])
    out = _run(client)
    assert not out.ok and out.error_kind == "blocked" and out.attempts == 2


def test_max_tokens_resends_task_with_shorter_instruction():
    client = ScriptedClient(
        [
            LLMResult(text="", model="m", latency_ms=1, finish_reason="MAX_TOKENS"),
            json.dumps(valid_explanation()),
        ]
    )
    out = _run(client)
    assert out.ok
    assert client.prompts[1].startswith("ORIGINAL PROMPT") and parsing.SHORTER_REPLY in client.prompts[1]


def test_rate_limit_wait_uses_retry_after_capped():
    assert parsing._wait_for(LLMError("rate_limit", retry_after=17), 0) == 17
    assert parsing._wait_for(LLMError("rate_limit", retry_after=500), 0) == 60
    assert parsing._wait_for(LLMError("rate_limit"), 0) == 15
    assert parsing._wait_for(LLMError("api_error"), 0) == 1
    assert parsing._wait_for(LLMError("timeout"), 1) == 3
