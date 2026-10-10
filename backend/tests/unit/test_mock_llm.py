"""The mock provider always produces schema-valid, semantically valid output (Section 8.9.4)."""

import json
from pathlib import Path

import pytest

from app.llm import parsing, prompt_builder
from app.llm.mock_client import FailingMockClient, FlakyMockClient, MockClient
from app.llm.output_schema import ExplanationOutput, RiskOnlyOutput
from app.pipeline.language import EXTENSION_MAP
from app.pipeline.redaction import redact, synthetic_findings
from app.pipeline.types import StaticFinding
from app.pipeline.validation import normalise
from tests.conftest import BENCHMARK_DIR, FIXTURES

SAMPLES = sorted((BENCHMARK_DIR / "samples").iterdir()) + sorted((FIXTURES / "code").iterdir())


def _static_for(code: str) -> list[StaticFinding]:
    findings = synthetic_findings(redact(code))
    for i, f in enumerate(findings, start=1):
        f.id = f"S{i}"
    return findings


@pytest.mark.parametrize("path", SAMPLES, ids=[p.name for p in SAMPLES])
def test_mock_output_valid_for_every_sample(path: Path):
    code = normalise(path.read_text(encoding="utf-8"))
    language = EXTENSION_MAP[path.suffix]
    redacted = redact(code).redacted_code
    static = _static_for(code)
    prompt = prompt_builder.explain_prompt(redacted, language, static, "v1")
    reply = MockClient().complete("sys", prompt).text
    check = parsing.explanation_checker(redacted, [f.id for f in static])
    value, errors = parsing.parse_reply(reply, ExplanationOutput, check, final_attempt=False)
    assert errors == [], errors
    assert value.breakdown and value.purpose_summary
    assert value.improved_code.strip() != redacted.strip()
    assert {a.static_id for a in value.static_assessment} == {f.id for f in static}
    assert "Mock explanation" in value.purpose_summary

    risks = MockClient().complete("sys", prompt_builder.risks_prompt(redacted, language, "v1")).text
    rvalue, rerrors = parsing.parse_reply(risks, RiskOnlyOutput, parsing.risks_checker(redacted), False)
    assert rerrors == []
    # Consistency run returns the same findings (consistency = 100%).
    assert [(f.start_line, f.cwe_id) for f in rvalue.findings] == [
        (f.start_line, f.cwe_id) for f in value.findings
    ]


def test_mock_breakdown_python_functions():
    code = (BENCHMARK_DIR / "samples" / "p01_user_lookup.py").read_text(encoding="utf-8").rstrip()
    reply = json.loads(MockClient().respond(prompt_builder.explain_prompt(code, "python", [], "v1")))
    titles = [s["title"] for s in reply["breakdown"]]
    assert titles == [
        "Imports and setup",
        "get_connection function",
        "find_user_by_username function",
        "count_users function",
    ]
    assert reply["breakdown"][0]["start_line"] == 1
    assert reply["breakdown"][-1]["end_line"] == code.count("\n") + 1


def test_mock_sql_fix_is_parameterised():
    code = (BENCHMARK_DIR / "samples" / "p01_user_lookup.py").read_text(encoding="utf-8").rstrip()
    reply = json.loads(MockClient().respond(prompt_builder.explain_prompt(code, "python", [], "v1")))
    assert 'WHERE username = ?"' in reply["improved_code"]
    assert "cursor.execute(query, (username,))" in reply["improved_code"]
    assert any(f["cwe_id"] == "CWE-89" for f in reply["findings"])
    assert reply["changes"][0]["original_lines"] == [20, 20]


def test_mock_uses_static_findings():
    code = "import os\n\ndef ping(h):\n    os.system('ping ' + h)\n"
    static = [
        StaticFinding(
            "S1",
            "bandit",
            "B605",
            "Starting a process with a shell.",
            4,
            4,
            "HIGH",
            "CWE-78",
            None,
            "security",
        )
    ]
    reply = json.loads(MockClient().respond(prompt_builder.explain_prompt(code, "python", static, "v1")))
    linked = [f for f in reply["findings"] if f["related_static_ids"] == ["S1"]]
    assert linked and linked[0]["cwe_id"] == "CWE-78" and linked[0]["category"] == "security"
    assert reply["static_assessment"] == [
        {
            "static_id": "S1",
            "verdict": "agree",
            "reason": "The flagged line matches a known risky pattern.",
        }
    ]


def test_mock_baseline_is_free_text():
    prompt = prompt_builder.baseline_prompt("def f(x):\n    return eval(x)", "python", "v1")
    text = MockClient().complete(None, prompt).text
    assert "Possible problems" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_flaky_and_failing_clients():
    code = "def f(x):\n    return x\n"
    prompt = prompt_builder.explain_prompt(code, "python", [], "v1")
    flaky = FlakyMockClient(failures=2)
    out = parsing.call_with_repair(
        flaky,
        "s",
        prompt,
        ExplanationOutput,
        parsing.explanation_checker(code, []),
        temperature=0.2,
        max_retries=2,
    )
    assert out.ok and out.attempts == 3
    failing = FailingMockClient()
    out = parsing.call_with_repair(
        failing, "s", prompt, ExplanationOutput, None, temperature=0.2, max_retries=2
    )
    assert not out.ok and out.error_kind == "api_error" and failing.calls == 3
