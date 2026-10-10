"""Health and meta endpoints."""


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["llm_provider"] == "mock"


def test_meta_shape(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert [lang["id"] for lang in body["languages"]] == [
        "python",
        "javascript",
        "java",
    ]
    assert body["max_lines"] == 400
    assert body["max_chars"] == 40000
    assert body["guest_retention_hours"] == 24
    assert "24 hours" in body["privacy_notice"]


def test_security_headers(client):
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-request-id"]


def test_unknown_api_path_returns_error_shape(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
