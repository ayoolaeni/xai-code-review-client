"""One test per functional / non-functional requirement where automatable (Section 16.1, 20).

Each test is named after the requirement ID so the results map directly onto docs/TEST_CASES.md.
"""

import pytest

from app.llm.client import set_client_override
from app.llm.mock_client import FailingMockClient, RecordingMockClient
from app.services import pdf_service
from tests.conftest import BENCHMARK_DIR, login, make_user

SQLI = (BENCHMARK_DIR / "samples" / "p01_user_lookup.py").read_text(encoding="utf-8")


def analyse(client, code=SQLI, **extra):
    r = client.post("/api/analyses", json={"code": code, **extra})
    assert r.status_code == 202, r.text
    return client.get(f"/api/analyses/{r.json()['public_id']}").json()


def test_FR1_paste_or_upload(client):
    assert analyse(client)["status"] == "completed"  # pasted
    assert analyse(client, filename="lookup.py")["submission"]["filename"] == "lookup.py"  # uploaded


def test_FR2_language_selection_and_detection(client):
    assert analyse(client, language="python")["submission"]["language_source"] == "user"
    auto = analyse(client)
    assert auto["submission"]["language"] == "python" and auto["submission"]["language_source"] == "auto"


def test_FR3_input_validation(client):
    for payload, code in [
        ({"code": " "}, "EMPTY_CODE"),
        ({"code": "x", "filename": "a.rb"}, "UNSUPPORTED_FILE_TYPE"),
        ({"code": "\n".join(["a = 1"] * 401), "language": "python"}, "INPUT_TOO_LONG"),
    ]:
        r = client.post("/api/analyses", json=payload)
        assert r.status_code == 422 and r.json()["error"]["code"] == code and r.json()["error"]["message"]


def test_FR4_secrets_masked_before_llm(client):
    recorder = RecordingMockClient()
    set_client_override(recorder)
    report = analyse(
        client, code='password = "S3cretValue99"\ndef f():\n    return password\n', language="python"
    )
    assert all("S3cretValue99" not in user for _, user in recorder.prompts)
    assert report["transparency"]["redaction"]["count"] == 1


def test_FR5_static_analysis_recorded(client):
    report = analyse(client)
    assert {t["tool"] for t in report["transparency"]["tools_run"]} == {"semgrep", "bandit"}
    static = [f for f in report["findings"] if f["source"] in ("static", "both")]
    assert static and all(f["static_rule_id"] and f["start_line"] for f in static)


def test_FR6_purpose_summary(client):
    assert len(analyse(client)["overview"]["purpose_summary"]) >= 10


def test_FR7_breakdown_with_line_ranges(client):
    sections = analyse(client)["breakdown"]
    assert sections and all(s["start_line"] <= s["end_line"] and s["explanation"] for s in sections)


def test_FR8_risks_have_all_fields(client):
    f = analyse(client)["findings"][0]
    for field in (
        "category",
        "start_line",
        "end_line",
        "description",
        "recommendation",
        "severity",
        "confidence",
    ):
        assert f[field]
    assert f["cwe"]["id"] == "CWE-89" and f["owasp_category"] == "A03:2021 – Injection"


def test_FR9_improved_code_with_reasons(client):
    improved = analyse(client)["improved"]
    assert improved["available"] and improved["improved_code"] and improved["changes"]
    assert all(c["reason"] for c in improved["changes"])


def test_FR10_overall_levels_limitations_and_review(client):
    o = analyse(client)
    assert o["overview"]["overall_risk_level"] == "CRITICAL" and o["overview"]["overall_confidence"]
    assert o["overview"]["human_review_advised"] is True and o["overview"]["review_reasons"]
    assert o["transparency"]["limitations"]


def test_FR11_source_of_each_finding(client):
    assert all(f["source"] in ("static", "llm", "both") for f in analyse(client)["findings"])


@pytest.mark.skipif(not pdf_service.is_available(), reason="WeasyPrint not installed")
def test_FR12_pdf_download(client):
    public_id = client.post("/api/analyses", json={"code": SQLI}).json()["public_id"]
    r = client.get(f"/api/analyses/{public_id}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_FR13_rate_and_comment(client):
    public_id = client.post("/api/analyses", json={"code": SQLI}).json()["public_id"]
    r = client.post(
        f"/api/analyses/{public_id}/feedback", json={"rating": 5, "was_helpful": True, "comment": "Clear"}
    )
    assert r.status_code == 200


def test_FR14_register_login_logout(client):
    assert (
        client.post(
            "/api/auth/register", json={"full_name": "R", "email": "r@example.com", "password": "Password123"}
        ).status_code
        == 201
    )
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    login(client, "r@example.com")


def test_FR15_history(client):
    make_user("h@example.com")
    login(client, "h@example.com")
    analyse(client)
    assert client.get("/api/history").json()["total"] == 1


def test_FR16_admin(client):
    login(client, "admin@example.com", "AdminPass123")
    assert client.get("/api/admin/users").status_code == 200
    assert client.get("/api/admin/stats").status_code == 200
    assert client.put("/api/admin/settings", json={"max_lines": 300}).status_code == 200


def test_NFR1_progress_stages_reported(client):
    from app.pipeline.stages import STAGES

    assert len(STAGES) == 11
    report = analyse(client)
    assert report["processing_time_ms"] is not None


def test_NFR3_transparency_every_finding(client):
    report = analyse(client)
    assert all(
        f["source"] and f["severity"] and f["confidence"] and f["confidence_reason"]
        for f in report["findings"]
    )
    assert len(report["transparency"]["limitations"]) >= 3


def test_NFR4_consistent_structure(client):
    from app.schemas import ReportOut

    for name in ("p01_user_lookup.py", "j04_orders_api.js", "V01UserDao.java"):
        code = (BENCHMARK_DIR / "samples" / name).read_text(encoding="utf-8")
        ReportOut.model_validate(analyse(client, code=code, filename=name))


def test_NFR5_security_headers_and_no_execution(client):
    r = client.get("/api/health")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert analyse(client)["transparency"]["code_executed"] is False


def test_NFR6_consent_respected(client):
    make_user("c@example.com")
    login(client, "c@example.com")
    assert analyse(client, store_code=False)["submission"]["original_code"] is None


def test_NFR7_fallback_when_llm_fails(client):
    set_client_override(FailingMockClient("api_error"))
    report = analyse(client)
    assert report["status"] == "completed" and report["overview"]["ai_explanation_available"] is False
    assert report["findings"] and report["overview"]["ai_unavailable_message"]


def test_NFR9_provider_is_replaceable(settings, monkeypatch):
    from app.llm.client import NotConfiguredClient, get_llm_client

    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert isinstance(get_llm_client(settings), NotConfiguredClient)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    assert get_llm_client(settings).name == "mock"
