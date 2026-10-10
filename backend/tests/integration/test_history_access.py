"""History (FR15), access control (12.12), consent (8.20, NFR6), retention (12.9) and rate limiting (7.3)."""

import datetime as dt

from app.db import SessionLocal
from app.models import AnalysisReport, Submission
from app.scheduler import run_retention
from tests.conftest import login, make_user

PY = "def add(a, b):\n    return a + b\n"


def _create(client, code=PY, **extra):
    r = client.post("/api/analyses", json={"code": code, "language": "python", **extra})
    assert r.status_code == 202, r.text
    return r.json()["public_id"]


# ---------- history ----------
def test_history_only_own_items_pagination_search_delete(client):
    make_user("alice@example.com")
    make_user("bob@example.com")
    login(client, "bob@example.com")
    _create(client)
    client.post("/api/auth/logout")
    client.cookies.clear()

    login(client, "alice@example.com")
    ids = [_create(client, f"def f{i}(x):\n    return x * {i}\n", filename=f"file{i}.py") for i in range(3)]
    r = client.get("/api/history?page=1&page_size=2")
    body = r.json()
    assert r.status_code == 200 and body["total"] == 3 and len(body["items"]) == 2
    assert body["items"][0]["public_id"] == ids[-1]  # newest first
    assert set(body["items"][0]) >= {
        "public_id",
        "submitted_at",
        "language",
        "filename",
        "line_count",
        "status",
        "overall_risk_level",
        "overall_confidence",
        "human_review_advised",
        "purpose_summary_preview",
    }
    assert client.get("/api/history?page=2&page_size=2").json()["items"][0]["public_id"] == ids[0]
    search = client.get("/api/history?q=FILE1").json()
    assert [i["filename"] for i in search["items"]] == ["file1.py"]
    assert client.get("/api/history?language=java").json()["total"] == 0

    assert client.delete(f"/api/analyses/{ids[0]}").status_code == 204
    assert client.get("/api/history").json()["total"] == 2
    assert client.get(f"/api/analyses/{ids[0]}").status_code == 404


def test_history_requires_login(client):
    r = client.get("/api/history")
    assert r.status_code == 401 and r.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ---------- access control ----------
def test_guest_report_readable_by_uuid(client):
    public_id = _create(client)
    client.cookies.clear()
    assert client.get(f"/api/analyses/{public_id}").status_code == 200


def test_owned_report_is_404_for_others_and_visible_to_admin(client):
    make_user("owner@example.com")
    make_user("other@example.com")
    login(client, "owner@example.com")
    public_id = _create(client)
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get(f"/api/analyses/{public_id}").status_code == 404  # anonymous
    login(client, "other@example.com")
    assert client.get(f"/api/analyses/{public_id}").status_code == 404  # another user
    assert client.delete(f"/api/analyses/{public_id}").status_code == 404
    client.cookies.clear()
    login(client, "admin@example.com", "AdminPass123")
    assert client.get(f"/api/analyses/{public_id}").status_code == 200


def test_guests_cannot_delete_reports(client):
    public_id = _create(client)
    assert client.delete(f"/api/analyses/{public_id}").status_code == 404


# ---------- consent ----------
def test_registered_without_consent_code_not_stored(client):
    make_user("private@example.com")
    login(client, "private@example.com")
    public_id = _create(client, store_code=False)
    report = client.get(f"/api/analyses/{public_id}").json()
    assert report["submission"]["code_stored"] is False
    assert report["submission"]["original_code"] is None
    assert report["submission"]["redacted_code"]  # the diff still works
    assert report["improved"]["available"] is True
    assert "not stored" in report["transparency"]["code_storage_note"]
    with SessionLocal() as db:
        assert db.query(Submission).one().code_text is None


def test_registered_default_consent_from_profile(client):
    make_user("keeper@example.com", store_code_default=True)
    login(client, "keeper@example.com")
    public_id = _create(client)
    assert client.get(f"/api/analyses/{public_id}").json()["submission"]["code_stored"] is True


# ---------- retention ----------
def test_retention_deletes_old_guest_reports_only(client):
    old_guest = _create(client)
    make_user("kept@example.com")
    login(client, "kept@example.com")
    old_user = _create(client, store_code=True)
    client.cookies.clear()
    fresh_guest = _create(client)
    old = dt.datetime.now(dt.UTC) - dt.timedelta(hours=25)
    with SessionLocal() as db:
        for pid in (old_guest, old_user):
            report = db.query(AnalysisReport).filter_by(public_id=pid).one()
            report.submission.submitted_at = old
        db.commit()
    # Expired guest reports are hidden immediately, even before the job runs.
    assert client.get(f"/api/analyses/{old_guest}").status_code == 404
    counts = run_retention()
    assert counts["guest_deleted"] == 1
    with SessionLocal() as db:
        assert db.query(AnalysisReport).filter_by(public_id=old_guest).one_or_none() is None
        assert db.query(AnalysisReport).filter_by(public_id=old_user).one_or_none() is not None
        assert db.query(AnalysisReport).filter_by(public_id=fresh_guest).one_or_none() is not None


def test_retention_cleans_stuck_jobs(client):
    with SessionLocal() as db:
        sub = Submission(
            language="python",
            language_source="user",
            code_text=PY,
            code_hash="x" * 64,
            line_count=2,
            char_count=len(PY),
            store_code=True,
        )
        db.add(sub)
        db.flush()
        db.add(
            AnalysisReport(
                submission_id=sub.submission_id,
                status="running",
                stage="static_analysis",
                llm_requests=0,
                redaction_count=0,
                created_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=45),
            )
        )
        db.commit()
    counts = run_retention()
    assert counts["stuck_failed"] == 1 and counts["stuck_deleted"] == 1


# ---------- rate limiting ----------
def test_guest_rate_limit_returns_429_with_retry_after(client):
    from app.services import settings_service

    with SessionLocal() as db:
        settings_service.update(db, {"guest_rate_limit_per_hour": 2}, None)
    for _ in range(2):
        _create(client)
    r = client.post("/api/analyses", json={"code": PY, "language": "python"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["Retry-After"]) > 0


def test_logged_in_users_have_their_own_limit(client):
    from app.services import settings_service

    with SessionLocal() as db:
        settings_service.update(db, {"guest_rate_limit_per_hour": 1, "user_rate_limit_per_hour": 3}, None)
    _create(client)  # guest uses the IP bucket
    make_user("busy@example.com")
    login(client, "busy@example.com")
    for _ in range(3):
        _create(client)
    assert client.post("/api/analyses", json={"code": PY, "language": "python"}).status_code == 429
