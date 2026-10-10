"""Auth integration tests (FR14)."""

from app.security import COOKIE_NAME
from tests.conftest import login, make_user


def _register(client, email="ada@example.com", password="Password123", **kw):
    return client.post(
        "/api/auth/register",
        json={"full_name": "Ada Lovelace", "email": email, "password": password, **kw},
    )


def test_register_sets_cookie_and_returns_user(client):
    r = _register(client, store_code_default=True)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "ada@example.com"
    assert body["role"] == "user"
    assert body["store_code_default"] is True
    assert "password_hash" not in body
    assert COOKIE_NAME in r.cookies
    cookie_header = r.headers["set-cookie"].lower()
    assert "httponly" in cookie_header and "samesite=lax" in cookie_header
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["full_name"] == "Ada Lovelace"


def test_register_email_is_lowercased_and_duplicate_rejected(client):
    assert _register(client, email="Ada@Example.com").status_code == 201
    r = _register(client, email="ada@example.COM")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_TAKEN"


def test_register_password_rules(client):
    for bad in ["short1", "lettersonly", "12345678901"]:
        r = _register(client, email=f"{bad}@example.com", password=bad)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_logout_me(client):
    make_user("bob@example.com")
    assert client.get("/api/auth/me").status_code == 401
    login(client, "bob@example.com")
    assert client.get("/api/auth/me").json()["email"] == "bob@example.com"
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_same_message(client):
    make_user("carol@example.com")
    r1 = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "Wrong12345"})
    r2 = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "Wrong12345"},
    )
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"] == "Incorrect email or password."


def test_inactive_user_cannot_login_and_token_rejected(client):
    from app.db import SessionLocal
    from app.models import User

    u = make_user("dave@example.com")
    login(client, "dave@example.com")
    with SessionLocal() as s:
        s.get(User, u.user_id).is_active = False
        s.commit()
    # Existing token is rejected for an inactive user.
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "Password123"})
    assert r.status_code == 403
    assert r.json()["error"]["message"] == "This account has been deactivated."


def test_update_me(client):
    make_user("erin@example.com")
    login(client, "erin@example.com")
    r = client.patch("/api/auth/me", json={"full_name": "Erin E.", "store_code_default": True})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Erin E." and r.json()["store_code_default"] is True


def test_admin_is_seeded(client):
    r = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_form_posts_rejected(client):
    r = client.post(
        "/api/auth/login",
        content="email=a@b.com&password=x",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415


def test_login_rate_limit(client):
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "Wrong12345"})
    r = client.post("/api/auth/login", json={"email": "x@example.com", "password": "Wrong12345"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["Retry-After"]) > 0
