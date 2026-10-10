"""POST /api/analyses validation and job status (Milestone 3)."""

PY = "import sqlite3\n\ndef get_user(name):\n    return name\n"


def test_post_returns_202_and_job_completes(client):
    r = client.post("/api/analyses", json={"code": PY})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued" and len(body["public_id"]) == 36
    status = client.get(f"/api/analyses/{body['public_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


def test_validation_errors_return_422_immediately(client):
    cases = [
        ({"code": "   "}, "EMPTY_CODE"),
        ({"code": "\n".join(["x = 1"] * 401), "language": "python"}, "INPUT_TOO_LONG"),
        ({"code": "print(1)", "filename": "evil.exe"}, "UNSUPPORTED_FILE_TYPE"),
        ({"code": "print(1)", "language": "ruby"}, "UNSUPPORTED_LANGUAGE"),
        ({"code": "hello there"}, "UNSUPPORTED_LANGUAGE"),
        ({"code": "a\x00b"}, "BINARY_CONTENT"),
        ({}, "VALIDATION_ERROR"),
    ]
    for payload, code in cases:
        r = client.post("/api/analyses", json=payload)
        assert r.status_code == 422, (payload, r.text)
        assert r.json()["error"]["code"] == code


def test_unknown_report_404(client):
    r = client.get("/api/analyses/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
