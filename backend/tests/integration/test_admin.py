"""Administrator features (FR16)."""

import pytest

from app.db import SessionLocal
from app.models import User
from tests.conftest import login, make_user


@pytest.fixture
def admin_client(client):
    login(client, "admin@example.com", "AdminPass123")
    return client


def _admin_id():
    with SessionLocal() as db:
        return db.query(User).filter_by(email="admin@example.com").one().user_id


def test_non_admin_forbidden(client):
    make_user("plain@example.com")
    login(client, "plain@example.com")
    for path in ("/api/admin/users", "/api/admin/stats", "/api/admin/settings"):
        r = client.get(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


def test_list_and_search_users_with_counts(admin_client):
    u = make_user("zed@example.com", full_name="Zed Zulu")
    admin_client.post("/api/analyses", json={"code": "def f():\n    return 1\n"})  # admin's own analysis
    body = admin_client.get("/api/admin/users?q=zulu").json()
    assert body["total"] == 1 and body["items"][0]["user_id"] == u.user_id
    assert body["items"][0]["analysis_count"] == 0
    everyone = admin_client.get("/api/admin/users").json()
    admin_row = next(i for i in everyone["items"] if i["email"] == "admin@example.com")
    assert admin_row["analysis_count"] == 1 and admin_row["role"] == "admin"


def test_change_role_and_deactivate(admin_client):
    u = make_user("member@example.com")
    r = admin_client.patch(f"/api/admin/users/{u.user_id}", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    r = admin_client.patch(f"/api/admin/users/{u.user_id}", json={"is_active": False})
    assert r.json()["is_active"] is False


def test_self_guards(admin_client):
    me = _admin_id()
    r = admin_client.patch(f"/api/admin/users/{me}", json={"role": "user"})
    assert r.status_code == 400 and "own administrator role" in r.json()["error"]["message"]
    r = admin_client.patch(f"/api/admin/users/{me}", json={"is_active": False})
    assert r.status_code == 400
    r = admin_client.delete(f"/api/admin/users/{me}")
    assert r.status_code == 400


def test_last_admin_guard(admin_client):
    other = make_user("second@example.com", role="admin")
    # Demoting the other admin is fine while I remain.
    assert admin_client.patch(f"/api/admin/users/{other.user_id}", json={"role": "user"}).status_code == 200


def test_delete_user_and_their_data(admin_client):
    u = make_user("gone@example.com")
    admin_client.cookies.clear()
    login(admin_client, "gone@example.com")
    public_id = admin_client.post("/api/analyses", json={"code": "def f():\n    return 1\n"}).json()[
        "public_id"
    ]
    admin_client.cookies.clear()
    login(admin_client, "admin@example.com", "AdminPass123")
    assert admin_client.delete(f"/api/admin/users/{u.user_id}").status_code == 204
    assert admin_client.get(f"/api/analyses/{public_id}").status_code == 404
    assert admin_client.delete(f"/api/admin/users/{u.user_id}").status_code == 404


def test_settings_validation_and_effect(admin_client):
    settings = admin_client.get("/api/admin/settings").json()
    keys = {s["key"] for s in settings}
    assert keys == {
        "max_lines",
        "max_chars",
        "guest_retention_hours",
        "guest_rate_limit_per_hour",
        "user_rate_limit_per_hour",
        "consistency_check_enabled",
        "enabled_tools",
        "llm_temperature",
    }
    max_lines = next(s for s in settings if s["key"] == "max_lines")
    assert max_lines["default"] == 400 and max_lines["min"] == 20 and max_lines["max"] == 2000

    for bad in (
        {"max_lines": 5},
        {"max_lines": "many"},
        {"llm_temperature": 2},
        {"unknown": 1},
        {"enabled_tools": {"python": ["eslint"]}},
        {"consistency_check_enabled": "yes"},
    ):
        r = admin_client.put("/api/admin/settings", json=bad)
        assert r.status_code == 422, bad

    r = admin_client.put("/api/admin/settings", json={"max_lines": 50})
    assert r.status_code == 200
    assert next(s for s in r.json() if s["key"] == "max_lines")["value"] == 50
    code = "\n".join(f"x{i} = {i}" for i in range(60))
    r = admin_client.post("/api/analyses", json={"code": code, "language": "python"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INPUT_TOO_LONG"
    assert admin_client.get("/api/meta").json()["max_lines"] == 50


def test_disabling_a_tool_marks_it_skipped(admin_client):
    admin_client.put(
        "/api/admin/settings",
        json={
            "enabled_tools": {
                "python": ["semgrep"],
                "javascript": ["semgrep", "eslint"],
                "java": ["semgrep", "pmd"],
            }
        },
    )
    public_id = admin_client.post("/api/analyses", json={"code": "def f():\n    return 1\n"}).json()[
        "public_id"
    ]
    tools = admin_client.get(f"/api/analyses/{public_id}").json()["transparency"]["tools_run"]
    assert {t["tool"]: t["status"] for t in tools}["bandit"] == "skipped"


def test_stats_shape(admin_client):
    admin_client.post("/api/analyses", json={"code": "def f():\n    return eval(input())\n"})
    s = admin_client.get("/api/admin/stats?days=30").json()
    assert s["range_days"] == 30
    assert set(s["totals"]) == {
        "analyses",
        "completed",
        "failed",
        "fallback",
        "registered_users",
        "guest_analyses",
    }
    assert s["totals"]["analyses"] == 1 and s["totals"]["completed"] == 1
    assert len(s["per_day"]) == 30 and s["per_day"][-1]["analyses"] == 1
    assert set(s["by_language"]) == {"python", "javascript", "java"}
    assert set(s["findings_by_severity"]) == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert set(s["findings_by_source"]) == {"static", "llm", "both"}
    assert set(s["feedback"]) == {"count", "avg_rating", "helpful_rate"}
    assert set(s["tool_failures"]) == {"semgrep", "bandit", "eslint", "pmd"}
    assert set(s["llm_usage_today"]) == {
        "requests",
        "limit",
        "input_tokens",
        "output_tokens",
    }
    assert isinstance(s["llm_usage_history"], list)
    assert s["avg_processing_ms"] is not None and s["human_review_advised_rate"] is not None
