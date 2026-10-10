"""Full analysis flow with SQLite + mock LLM (Section 16.2)."""

import pytest

from app.llm.client import set_client_override
from app.llm.mock_client import FailingMockClient, FlakyMockClient, RecordingMockClient
from app.schemas import ReportOut
from tests.conftest import BENCHMARK_DIR

SAMPLES = {
    "python": "p01_user_lookup.py",
    "javascript": "j02_formula.js",
    "java": "V06PasswordHasher.java",
}


def analyse(client, filename=None, code=None, **extra):
    if code is None:
        code = (BENCHMARK_DIR / "samples" / filename).read_text(encoding="utf-8")
    r = client.post("/api/analyses", json={"code": code, "filename": filename, **extra})
    assert r.status_code == 202, r.text
    public_id = r.json()["public_id"]
    report = client.get(f"/api/analyses/{public_id}")
    assert report.status_code == 200
    return public_id, report.json()


@pytest.mark.parametrize("language,filename", SAMPLES.items())
def test_full_flow_matches_contract(client, language, filename):
    _, body = analyse(client, filename)
    report = ReportOut.model_validate(body)  # Section 9 contract
    assert report.status == "completed"
    assert report.submission.language == language
    assert report.overview.ai_explanation_available is True
    assert report.breakdown, "breakdown must not be empty"
    assert report.findings, "seeded weakness should be found"
    # NFR3: every finding has source, severity and confidence; every report states limitations.
    for f in report.findings:
        assert f.source and f.severity and f.confidence and f.confidence_reason
    assert len(report.transparency.limitations) >= 3
    assert report.transparency.code_executed is False
    assert report.transparency.prompt_version == "v1"
    assert report.transparency.model_name == "mock-v1"
    assert report.improved.available and report.improved.check.syntax_ok in (True, None)
    assert report.owner == "guest" and report.expires_at is not None
    keys = [f.key for f in report.findings]
    assert keys == [f"F{i}" for i in range(1, len(keys) + 1)]


def test_python_sql_injection_report(client):
    _, body = analyse(client, "p01_user_lookup.py")
    f1 = body["findings"][0]
    assert f1["cwe"]["id"] == "CWE-89" and f1["severity"] == "CRITICAL"
    assert body["overview"]["overall_risk_level"] == "CRITICAL"
    assert body["overview"]["human_review_advised"] is True
    assert body["improved"]["requires_acknowledgement"] is True
    assert body["transparency"]["consistency"]["run_b_ok"] is True


def test_fallback_when_llm_fails(client):
    set_client_override(FailingMockClient("api_error"))
    _, body = analyse(client, "p01_user_lookup.py")
    report = ReportOut.model_validate(body)
    assert report.status == "completed"
    assert report.overview.ai_explanation_available is False
    assert report.overview.ai_unavailable_reason == "api_error"
    assert report.overview.overall_confidence == "LOW"
    assert report.breakdown == [] and report.improved.available is False
    assert any("could not be produced" in r for r in report.overview.review_reasons)
    assert report.overview.ai_unavailable_message
    for f in report.findings:  # static findings only
        assert f.source == "static" and f.ai_assessment == "not_reviewed" and f.confidence == "MEDIUM"


@pytest.mark.parametrize(
    "kind,text",
    [
        ("quota_exhausted", "free AI quota for today has been used up"),
        ("rate_limit", "The AI service is busy"),
        ("model_not_found", "configured AI model is not available"),
        ("blocked", "declined to analyse this code"),
    ],
)
def test_fallback_messages(client, kind, text):
    set_client_override(FailingMockClient(kind))
    _, body = analyse(client, "p02_ping_tool.py")
    assert body["overview"]["ai_unavailable_reason"] == kind
    assert text in body["overview"]["ai_unavailable_message"]
    if kind == "quota_exhausted":
        assert body["overview"]["ai_unavailable_until"] is not None


def test_repair_succeeds_after_two_invalid_replies(client):
    flaky = FlakyMockClient(failures=2)
    set_client_override(flaky)
    _, body = analyse(client, "p01_user_lookup.py")
    assert body["overview"]["ai_explanation_available"] is True
    assert body["transparency"]["llm_requests"] >= 3


def test_three_invalid_replies_fall_back(client):
    set_client_override(FlakyMockClient(failures=3))
    _, body = analyse(client, "p01_user_lookup.py")
    assert body["overview"]["ai_explanation_available"] is False
    assert body["overview"]["ai_unavailable_reason"] == "invalid_output"


def test_secrets_never_reach_the_llm(client):
    recorder = RecordingMockClient()
    set_client_override(recorder)
    code = (BENCHMARK_DIR / "samples" / "p03_db_config.py").read_text(encoding="utf-8")
    _, body = analyse(client, "p03_db_config.py", code=code)
    assert recorder.prompts
    for _system, user in recorder.prompts:
        assert "Winter2024!Reports" not in user and "ex_7f3a9c2b8d1e4f60a5b7c9d2e1f3a4b5" not in user
        assert "[REDACTED_ASSIGNED_SECRET]" in user
    assert body["transparency"]["redaction"]["count"] == 2
    assert body["submission"]["original_code"] == code.rstrip()  # original kept on the server for guests
    assert "Winter2024!Reports" not in body["submission"]["redacted_code"]


def test_consistency_disabled_by_admin(client):
    from app.db import SessionLocal
    from app.services import settings_service

    with SessionLocal() as db:
        settings_service.update(db, {"consistency_check_enabled": False}, None)
    _, body = analyse(client, "p01_user_lookup.py")
    c = body["transparency"]["consistency"]
    assert c["enabled"] is False
    assert body["transparency"]["llm_requests"] == 1


def test_status_while_queued(app):
    """Without running the job, GET returns the AnalysisStatus shape."""
    from fastapi.testclient import TestClient

    from app.services.analysis_service import JobRunner, get_job_runner

    class NoRun(JobRunner):
        def __init__(self):
            import threading
            from collections import deque

            self._waiting = deque()
            self._lock = threading.Lock()

        def submit(self, public_id):
            self._waiting.append(public_id)

    runner = NoRun()
    app.dependency_overrides[get_job_runner] = lambda: runner
    with TestClient(app) as c:
        r1 = c.post("/api/analyses", json={"code": "def f():\n    return 1\n"})
        r2 = c.post("/api/analyses", json={"code": "def g():\n    return 2\n"})
        status = c.get(f"/api/analyses/{r2.json()['public_id']}").json()
    assert status["status"] == "queued" and status["queue_position"] == 2
    assert status["stage_count"] == 11 and status["stage_label"] == "Checking your code"
    assert r1.status_code == 202
