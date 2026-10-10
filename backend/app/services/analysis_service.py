"""Create analysis jobs and run them on a bounded FIFO worker pool (Sections 5 and 8.9.6)."""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AnalysisReport, Submission, User
from app.pipeline import language, validation
from app.schemas import AnalysisCreate
from app.services import settings_service

log = logging.getLogger(__name__)


class JobRunner:
    """Runs analysis jobs in a thread pool. Extra jobs wait (status "queued") in FIFO order."""

    def __init__(self, max_workers: int):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="analysis")
        self._waiting: deque[str] = deque()
        self._lock = threading.Lock()

    def submit(self, public_id: str) -> None:
        with self._lock:
            self._waiting.append(public_id)
        self._executor.submit(self._run, public_id)

    def _run(self, public_id: str) -> None:
        from app.pipeline.orchestrator import run_job

        with self._lock:
            try:
                self._waiting.remove(public_id)
            except ValueError:
                pass
        run_job(public_id)

    def queue_position(self, public_id: str) -> int | None:
        with self._lock:
            try:
                return self._waiting.index(public_id) + 1
            except ValueError:
                return None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class InlineJobRunner(JobRunner):
    """Runs the job synchronously inside the request (used by tests and scripts)."""

    def __init__(self):  # noqa: D401 - no pool needed
        self._waiting = deque()
        self._lock = threading.Lock()

    def submit(self, public_id: str) -> None:
        from app.pipeline.orchestrator import run_job

        run_job(public_id)

    def shutdown(self) -> None:
        pass


_runner: JobRunner | None = None
_runner_lock = threading.Lock()


def get_job_runner() -> JobRunner:
    """FastAPI dependency (tests override it with InlineJobRunner)."""
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = JobRunner(max_workers=max(1, get_settings().LLM_MAX_CONCURRENT_JOBS))
        return _runner


def create_analysis(
    db: Session, body: AnalysisCreate, user: User | None, ip_hash: str | None
) -> AnalysisReport:
    """Validate synchronously (FR3 errors return 422 immediately) and create the queued job."""
    values = settings_service.get(db)
    # SECURITY: never execute user code — it is only validated and stored as text.
    v = validation.validate(
        body.code,
        body.language,
        body.filename,
        values["max_lines"],
        values["max_chars"],
    )
    lang = language.resolve(v.code, v.language, v.filename)

    if user is not None:
        store_code = body.store_code if body.store_code is not None else user.store_code_default
    else:
        store_code = True  # guests: kept until the retention job deletes it (needed to show the report)

    settings = get_settings()
    submission = Submission(
        user_id=user.user_id if user else None,
        language=lang.language,
        language_source=lang.source,
        filename=v.filename,
        code_text=v.code,  # always the original; nulled after the job if no consent (8.20)
        code_hash=hashlib.sha256(v.code.encode("utf-8")).hexdigest(),
        line_count=v.line_count,
        char_count=v.char_count,
        store_code=store_code,
        client_ip_hash=ip_hash,
    )
    db.add(submission)
    db.flush()
    report = AnalysisReport(
        submission_id=submission.submission_id,
        status="queued",
        stage="validating",
        llm_provider=settings.LLM_PROVIDER,
        prompt_version=settings.PROMPT_VERSION,
        llm_requests=0,
        redaction_count=0,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    log.info(
        "analysis created",
        extra={"event": "analysis_created", "public_id": report.public_id},
    )
    return report
