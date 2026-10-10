"""Application settings loaded from environment variables (Section 4)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env next to the backend folder, or in the repository root
        env_file=(str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ---------- General ----------
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_BASE_URL: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"
    LOG_PROMPTS: bool = False

    # ---------- Database ----------
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # ---------- Security ----------
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 720
    COOKIE_SECURE: bool = False
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "ChangeMe123!"
    ADMIN_NAME: str = "System Administrator"
    BCRYPT_ROUNDS: int = 12  # (ops) lowered in tests for speed

    # ---------- LLM ----------
    LLM_PROVIDER: Literal["gemini", "mock", "openai", "anthropic"] = "gemini"
    LLM_MODEL: str = "gemini-flash-latest"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_OUTPUT_TOKENS: int = 8192

    # ---------- Gemini free-tier pacing ----------
    GEMINI_REQUESTS_PER_MINUTE: int = 8
    GEMINI_REQUESTS_PER_DAY: int = 900
    GEMINI_THINKING: Literal["off", "low", "default"] = "low"
    LLM_MAX_CONCURRENT_JOBS: int = 2
    LLM_TIMEOUT_SECONDS: int = 90
    LLM_MAX_RETRIES: int = 2
    PROMPT_VERSION: str = "v1"

    # ---------- Static analysis ----------
    SEMGREP_USE_REGISTRY: bool = True
    STATIC_TOOL_TIMEOUT_SECONDS: int = 30
    ESLINT_DIR: str = "/opt/eslint"
    PMD_BIN: str = "/opt/pmd/bin/pmd"

    # ---------- Defaults for admin-editable settings ----------
    DEFAULT_MAX_LINES: int = 400
    DEFAULT_MAX_CHARS: int = 40000
    DEFAULT_GUEST_RETENTION_HOURS: int = 24
    DEFAULT_GUEST_RATE_LIMIT_PER_HOUR: int = 10
    DEFAULT_USER_RATE_LIMIT_PER_HOUR: int = 30
    DEFAULT_CONSISTENCY_CHECK_ENABLED: bool = True

    # ---------- Operational ----------
    STATIC_DIR: str = str(BACKEND_DIR / "static")  # built frontend served in production
    SCHEDULER_ENABLED: bool = True

    @field_validator("*", mode="before")
    @classmethod
    def _strip_inline_comments(cls, v):
        # Some .env parsers keep "# comment" as the value of an empty variable.
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("#"):
                return ""
            return stripped
        return v

    # ---------- Derived values ----------
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def eslint_dir(self) -> Path:
        """ESLINT_DIR if it exists, otherwise the in-repo folder used in development."""
        if self.ESLINT_DIR and Path(self.ESLINT_DIR).is_dir():
            return Path(self.ESLINT_DIR)
        return APP_DIR / "static_analysis" / "eslint"

    @property
    def static_dir(self) -> Path:
        """STATIC_DIR if it holds a built frontend, otherwise frontend/dist of the repository (local build)."""
        configured = Path(self.STATIC_DIR)
        local_build = BACKEND_DIR.parent / "frontend" / "dist"
        if not (configured / "index.html").is_file() and (local_build / "index.html").is_file():
            return local_build
        return configured

    @property
    def llm_api_key(self) -> str:
        return {
            "gemini": self.GEMINI_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "mock": "not-needed",
        }[self.LLM_PROVIDER]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    def check_startup(self) -> None:
        """Fail fast on unsafe production configuration (Section 4)."""
        if self.is_production:
            problems = []
            if self.JWT_SECRET == DEFAULT_JWT_SECRET or len(self.JWT_SECRET) < 16:
                problems.append("JWT_SECRET must be changed to a long random string.")
            if not self.COOKIE_SECURE:
                problems.append("COOKIE_SECURE must be true in production (HTTPS).")
            if self.LLM_PROVIDER != "mock" and not self.llm_api_key:
                key_name = f"{self.LLM_PROVIDER.upper()}_API_KEY"
                problems.append(f"{key_name} must be set when LLM_PROVIDER={self.LLM_PROVIDER}.")
            if problems:
                raise RuntimeError("Unsafe production configuration: " + " ".join(problems))
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            log.warning(
                "GEMINI_API_KEY is empty: AI explanations are disabled and every analysis will use the "
                "static-only fallback. Get a free key from Google AI Studio (README, Appendix A)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
