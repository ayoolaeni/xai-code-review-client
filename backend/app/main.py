"""FastAPI application factory, routers and single-origin SPA serving (Section 5)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_db, run_migrations
from app.errors import error_body, register_error_handlers
from app.logging_config import configure_logging
from app.middleware import install_middleware
from app.rate_limit import limiter, rate_limit_handler
from app.routers import admin, analyses, auth, history, meta

log = logging.getLogger(__name__)


def _startup() -> None:
    from app.seed import seed

    settings = get_settings()
    settings.check_startup()
    run_migrations()
    init_db()
    with SessionLocal() as db:
        seed(db)
    # Detect installed tools once (cached; shown in /api/health).
    from app.static_analysis.registry import tool_availability, tool_versions

    log.info("static analysis tools: %s", tool_versions())
    tool_availability()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app import scheduler

    _startup()
    if get_settings().SCHEDULER_ENABLED:
        scheduler.start()
    yield
    scheduler.stop()


def create_app(run_startup: bool = True) -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Explainable AI Code Review Assistant",
        version="1.0.0",
        lifespan=lifespan if run_startup else None,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    register_error_handlers(app)
    install_middleware(app)

    app.include_router(meta.router)
    app.include_router(auth.router)
    app.include_router(analyses.router)
    app.include_router(history.router)
    app.include_router(admin.router)

    _mount_spa(app, settings.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built frontend: real files when they exist, otherwise index.html (client routing)."""

    @app.get("/{full_path:path}", include_in_schema=False)
    @limiter.exempt
    async def spa(full_path: str, request: Request):
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse(
                status_code=404,
                content=error_body("NOT_FOUND", "Unknown API endpoint."),
            )
        index = static_dir / "index.html"
        if full_path:
            candidate = (static_dir / full_path).resolve()
            # Only serve files that are really inside the static folder.
            if static_dir.resolve() in candidate.parents and candidate.is_file():
                headers = {}
                if full_path.startswith("assets/"):
                    headers["Cache-Control"] = "public, max-age=31536000, immutable"
                return FileResponse(candidate, headers=headers)
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return JSONResponse(
            status_code=404,
            content=error_body(
                "NOT_FOUND",
                "The frontend has not been built. In development open http://localhost:5173 instead.",
            ),
        )


app = create_app()
