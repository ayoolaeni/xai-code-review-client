"""PDF export (FR12) and feedback (FR13)."""

import pytest

from app.services import pdf_service
from tests.conftest import BENCHMARK_DIR

PDF_OK = pdf_service.is_available()


def _analyse(client, name="p01_user_lookup.py"):
    code = (BENCHMARK_DIR / "samples" / name).read_text(encoding="utf-8")
    return client.post("/api/analyses", json={"code": code, "filename": name}).json()["public_id"]


def test_pdf_html_contains_every_section(client):
    public_id = _analyse(client)
    report = client.get(f"/api/analyses/{public_id}").json()
    html = pdf_service.render_html(report)
    for heading in [
        "1. Code",
        "2. Breakdown",
        "3. Findings",
        "4. Improved code",
        "5. Transparency",
    ]:
        assert heading in html
    assert "Severity: Critical" in html and "Review the critical findings before using this code." in html
    assert "SQL injection" in html


def test_pdf_html_escapes_user_code(client):
    code = "def f():\n    return '<script>alert(1)</script>'\n"
    public_id = client.post("/api/analyses", json={"code": code, "language": "python"}).json()["public_id"]
    html = pdf_service.render_html(client.get(f"/api/analyses/{public_id}").json())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.skipif(not PDF_OK, reason="WeasyPrint native libraries (Pango) not installed")
def test_pdf_download(client):
    public_id = _analyse(client)
    r = client.get(f"/api/analyses/{public_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert f"xai-report-{public_id[:8]}.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF") and len(r.content) > 5 * 1024


@pytest.mark.skipif(PDF_OK, reason="only on servers without WeasyPrint")
def test_pdf_unavailable_gives_clear_error(client):
    public_id = _analyse(client)
    r = client.get(f"/api/analyses/{public_id}/pdf")
    assert r.status_code == 503 and r.json()["error"]["code"] == "PDF_UNAVAILABLE"


def test_pdf_409_before_completion(app):
    from fastapi.testclient import TestClient

    from app.services.analysis_service import InlineJobRunner, get_job_runner

    class NoRun(InlineJobRunner):
        def submit(self, public_id):
            pass

    app.dependency_overrides[get_job_runner] = lambda: NoRun()
    with TestClient(app) as c:
        public_id = c.post("/api/analyses", json={"code": "def f():\n    return 1\n"}).json()["public_id"]
        r = c.get(f"/api/analyses/{public_id}/pdf")
    assert r.status_code == 409 and r.json()["error"]["code"] == "REPORT_NOT_READY"


def test_guest_feedback_create_and_update(client):
    public_id = _analyse(client)
    r = client.post(
        f"/api/analyses/{public_id}/feedback",
        json={"rating": 4, "was_helpful": True, "comment": "Nice"},
    )
    assert r.status_code == 200
    token = r.json()["feedback_token"]
    assert token
    r2 = client.post(
        f"/api/analyses/{public_id}/feedback",
        json={
            "rating": 2,
            "was_helpful": False,
            "comment": "",
            "feedback_token": token,
        },
    )
    assert r2.json()["feedback_id"] == r.json()["feedback_id"]  # same row updated
    report = client.get(f"/api/analyses/{public_id}?ft={token}").json()
    assert report["feedback"] == {"rating": 2, "was_helpful": False, "comment": None}
    # Without the token the viewer has no feedback yet.
    assert client.get(f"/api/analyses/{public_id}").json()["feedback"]["rating"] is None


def test_feedback_validation(client):
    public_id = _analyse(client)
    for bad in [
        {"rating": 0, "was_helpful": True},
        {"rating": 6, "was_helpful": True},
        {"rating": 3},
    ]:
        r = client.post(f"/api/analyses/{public_id}/feedback", json=bad)
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.post(
        f"/api/analyses/{public_id}/feedback",
        json={"rating": 3, "was_helpful": True, "comment": "x" * 2001},
    )
    assert r.status_code == 422


def test_registered_user_feedback_upserts(client):
    from tests.conftest import login, make_user

    make_user("fb@example.com")
    login(client, "fb@example.com")
    public_id = _analyse(client)
    a = client.post(f"/api/analyses/{public_id}/feedback", json={"rating": 5, "was_helpful": True}).json()
    b = client.post(f"/api/analyses/{public_id}/feedback", json={"rating": 3, "was_helpful": True}).json()
    assert a["feedback_id"] == b["feedback_id"] and a["feedback_token"] is None
    assert client.get(f"/api/analyses/{public_id}").json()["feedback"]["rating"] == 3
