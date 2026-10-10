"""Shared test fixtures. Tests always use SQLite and the mock LLM provider (never the real Gemini API)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Must be set before the app is imported.
_TMP = Path(tempfile.mkdtemp(prefix="xai-tests-"))
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{(_TMP / 'boot.db').as_posix()}",
        "LLM_PROVIDER": "mock",
        "GEMINI_API_KEY": "",
        "BCRYPT_ROUNDS": "4",
        "SCHEDULER_ENABLED": "false",
        "SEMGREP_USE_REGISTRY": "false",
        "JWT_SECRET": "test-secret-for-the-test-suite-only",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_PASSWORD": "AdminPass123",
        "LOG_LEVEL": "WARNING",
        "STATIC_DIR": str(_TMP / "no-static"),
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402
from app.rate_limit import limiter  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import settings_service  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "evaluation" / "benchmark"


@pytest.fixture(autouse=True)
def _llm_isolation(monkeypatch):
    """No real waiting between LLM retries, and a fresh client / rate limiter for every test."""
    from app.llm import parsing, rate_limiter
    from app.llm.client import set_client_override

    monkeypatch.setattr(parsing, "sleep_fn", lambda _s: None)
    rate_limiter.reset_for_tests()
    set_client_override(None)
    yield
    set_client_override(None)
    rate_limiter.reset_for_tests()


@pytest.fixture
def db_engine(tmp_path):
    engine = init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    settings_service.invalidate_cache()
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(db_engine):
    from app.main import create_app
    from app.seed import seed

    with SessionLocal() as s:
        seed(s)
    from app.services.analysis_service import InlineJobRunner, get_job_runner

    limiter.reset()
    limiter.enabled = True
    application = create_app(run_startup=False)
    # Run the background job synchronously so tests can check the finished report (Section 16.2).
    inline = InlineJobRunner()
    application.dependency_overrides[get_job_runner] = lambda: inline
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def make_user(email: str, password: str = "Password123", role: str = "user", **kw) -> User:
    with SessionLocal() as s:
        user = User(
            full_name=kw.pop("full_name", email.split("@")[0].title()),
            email=email.lower(),
            password_hash=hash_password(password),
            role=role,
            **kw,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def login(client: TestClient, email: str, password: str = "Password123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


@pytest.fixture
def settings():
    return get_settings()
