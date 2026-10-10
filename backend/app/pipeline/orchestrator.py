"""Runs the pipeline stages in order and records progress (Section 8).

Stage order: validating → detecting_language → masking_secrets → static_analysis → generating_explanation
(+ checking_consistency in parallel) → merging_findings → scoring → verifying_improved_code → saving → completed.
"""

from __future__ import annotations

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.config import get_settings
from app.db import SessionLocal
from app.llm import parsing, prompt_builder
from app.llm.client import get_llm_client
from app.llm.output_schema import ExplanationOutput, RiskOnlyOutput
from app.llm.rate_limiter import consistency_should_run, get_quota
from app.models import (
    AnalysisReport,
    CodeSection,
    Finding,
    ImprovedVersion,
    Submission,
    utcnow,
)
from app.pipeline import (
    fallback,
    language,
    limitations,
    merge,
    redaction,
    review_rule,
    scoring,
    validation,
    verify_improved,
)
from app.pipeline.types import ReportFinding
from app.services import settings_service
from app.static_analysis.registry import run_static_analysis

log = logging.getLogger(__name__)

FAILED_MESSAGE = "Something went wrong while analysing your code. Please try again."


def set_stage(public_id: str, stage: str, **fields) -> None:
    """Commit the new stage immediately so polling clients see it."""
    with SessionLocal() as db:
        report = db.query(AnalysisReport).filter_by(public_id=public_id).one()
        report.stage = stage
        for key, value in fields.items():
            setattr(report, key, value)
        db.commit()


@dataclass
class JobInput:
    public_id: str
    code: str
    language: str
    language_source: str
    filename: str | None
    is_registered: bool
    store_code: bool


@dataclass
class JobResult:
    """Everything the saving stage writes."""

    purpose_summary: str
    sections: list[dict]
    findings: list[ReportFinding]
    improved_code: str | None
    changes: list[dict]
    overall_risk: str
    overall_confidence: str
    review_reasons: list[str]
    limitations: list[str]
    ai_available: bool
    ai_reason: str | None
    ai_until: object | None
    model_name: str
    provider: str
    llm_requests: int
    tools_run: list[dict]
    consistency: dict
    improved_check: dict | None
    redaction_count: int
    redaction_by_type: dict
    redacted_code: str
    domains: list[str]


def _load(public_id: str) -> JobInput | None:
    with SessionLocal() as db:
        report = db.query(AnalysisReport).filter_by(public_id=public_id).one_or_none()
        if report is None:
            return None
        sub = report.submission
        return JobInput(
            public_id=public_id,
            code=sub.code_text or "",
            language=sub.language,
            language_source=sub.language_source,
            filename=sub.filename,
            is_registered=sub.user_id is not None,
            store_code=sub.store_code,
        )


def analyse(job: JobInput, progress=lambda stage: None) -> JobResult:
    """The pipeline itself (stages 1–9). `progress(stage)` is called before each stage starts."""
    settings = get_settings()

    progress("validating")
    # SECURITY: never execute user code — validation only inspects the text.
    code = validation.normalise(job.code)

    progress("detecting_language")
    chosen = job.language if job.language_source == "user" else "auto"
    lang = language.resolve(code, chosen, job.filename)

    progress("masking_secrets")
    red = redaction.redact(code)

    progress("static_analysis")
    with SessionLocal() as db:
        values = settings_service.get(db)
    enabled = values["enabled_tools"].get(lang.language, [])
    static = run_static_analysis(code, lang.language, enabled, redaction.synthetic_findings(red))
    # Tool messages can quote the secret (e.g. Bandit B105) — mask them before the prompt and the database.
    for f in static.findings:
        f.message = redaction.mask_secrets(f.message, red.secrets)

    # ---------- AI explanation + consistency check (in parallel) ----------
    progress("generating_explanation")
    client = get_llm_client()
    version = settings.PROMPT_VERSION
    temperature = float(values["llm_temperature"])
    system = prompt_builder.system_prompt(version)
    explain_prompt = prompt_builder.explain_prompt(red.redacted_code, lang.language, static.findings, version)
    static_ids = [f.id for f in static.findings]
    consistency_enabled = bool(values["consistency_check_enabled"])
    consistency_reason = None if consistency_enabled else "turned off by the administrator"
    if consistency_enabled:
        consistency_enabled, consistency_reason = consistency_should_run()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"llm-{job.public_id[:8]}") as pool:
        main_future = pool.submit(
            parsing.call_with_repair,
            client,
            system,
            explain_prompt,
            ExplanationOutput,
            parsing.explanation_checker(red.redacted_code, static_ids),
            temperature=temperature,
            prompt_version=version,
        )
        b_future = None
        if consistency_enabled:
            b_future = pool.submit(
                parsing.call_with_repair,
                client,
                system,
                prompt_builder.risks_prompt(red.redacted_code, lang.language, version),
                RiskOnlyOutput,
                parsing.risks_checker(red.redacted_code),
                temperature=temperature,
                prompt_version=version,
            )
        main = main_future.result()
        progress("checking_consistency")
        run_b = b_future.result() if b_future else None

    llm_requests = main.attempts + (run_b.attempts if run_b else 0)
    log.info(
        "llm finished",
        extra={
            "event": "llm_done",
            "public_id": job.public_id,
            "status": "ok" if main.ok else main.error_kind,
            "llm_attempts": llm_requests,
            "llm_latency_ms": main.latency_ms,
            "tokens_in": main.tokens_in,
            "tokens_out": main.tokens_out,
        },
    )

    explanation: ExplanationOutput | None = main.value if main.ok else None  # type: ignore[assignment]
    ai_available = explanation is not None
    ai_reason = None
    ai_until = None
    fallback_message = None
    if not ai_available:
        ai_reason = main.error_kind or "api_error"
        if ai_reason == "auth" and not settings.llm_configured:
            fallback_message = fallback.message("not_configured")
        else:
            if ai_reason == "quota_exhausted":
                ai_until = get_quota().reset_time_utc()
            fallback_message = fallback.message(ai_reason, ai_until)

    # ---------- merge ----------
    progress("merging_findings")
    if not ai_available:
        consistency = merge.consistency_not_run(consistency_enabled, 0, consistency_reason, None)
        consistency_state = "disabled"
    elif not consistency_enabled:
        consistency = merge.consistency_not_run(False, len(explanation.findings), consistency_reason, None)
        consistency_state = "disabled"
    elif run_b is None or not run_b.ok:
        consistency = merge.consistency_not_run(True, len(explanation.findings), None, False)
        consistency_state = "failed"
    else:
        consistency = merge.match_consistency(explanation.findings, run_b.value.findings)  # type: ignore[union-attr]
        consistency_state = "ran"
    findings, changes = merge.merge(static.findings, explanation, consistency)

    # ---------- scoring + human-review rule ----------
    progress("scoring")
    scoring.score(findings, consistency_state)
    findings, changes = merge.assign_keys(findings, changes)
    domains = review_rule.merge_domains(list(explanation.sensitive_domains) if explanation else [], code)
    reasons = review_rule.review_reasons(findings, domains, ai_available, fallback_message)

    # ---------- improved code ----------
    progress("verifying_improved_code")
    improved_check = None
    improved_code = explanation.improved_code if explanation else None
    if improved_code is not None:
        improved_check = verify_improved.verify(
            improved_code, lang.language, enabled, [f.cwe_id for f in findings]
        )

    notes = limitations.build(
        limitations.LimitationContext(
            provider=settings.LLM_PROVIDER,
            tool_runs=static.tool_runs,
            redaction_count=red.count,
            language=lang.language,
            language_source=lang.source,
            language_notes=lang.notes,
            consistency=consistency.to_dict(),
            improved_check=improved_check,
            java_wrapped=static.wrapped,
            fallback_message=fallback_message,
            ai_limitations=list(explanation.limitations) if explanation else [],
        )
    )

    return JobResult(
        purpose_summary=(explanation.purpose_summary if explanation else fallback.PURPOSE),
        sections=[s.model_dump() for s in explanation.breakdown] if explanation else [],
        findings=findings,
        improved_code=improved_code,
        changes=changes,
        overall_risk=scoring.overall_risk(findings),
        overall_confidence=scoring.overall_confidence(findings, ai_available),
        review_reasons=reasons,
        limitations=notes,
        ai_available=ai_available,
        ai_reason=ai_reason,
        ai_until=ai_until,
        model_name=main.model or getattr(client, "resolved_model", None) or client.model,
        provider=client.name,
        llm_requests=llm_requests,
        tools_run=[r.to_dict() for r in static.tool_runs],
        consistency=consistency.to_dict(),
        improved_check=improved_check,
        redaction_count=red.count,
        redaction_by_type=red.by_type,
        redacted_code=red.redacted_code,
        domains=domains,
    )


def save(job: JobInput, result: JobResult, started: float) -> None:
    """Stage 10: everything in one transaction."""
    with SessionLocal() as db:
        report = db.query(AnalysisReport).filter_by(public_id=job.public_id).one()
        report.purpose_summary = result.purpose_summary
        report.overall_risk_level = result.overall_risk
        report.overall_confidence = result.overall_confidence
        report.human_review_advised = len(result.review_reasons) > 0
        report.review_reasons = result.review_reasons
        report.limitations_note = result.limitations
        report.ai_explanation_available = result.ai_available
        report.ai_unavailable_reason = result.ai_reason
        report.ai_unavailable_until = result.ai_until
        report.model_name = (result.model_name or "")[:100]
        report.llm_provider = result.provider
        report.llm_requests = result.llm_requests
        report.prompt_version = get_settings().PROMPT_VERSION
        report.tools_run = result.tools_run
        report.consistency = result.consistency
        report.improved_code_check = result.improved_check
        report.redaction_count = result.redaction_count
        report.redaction_by_type = result.redaction_by_type
        report.redacted_code = result.redacted_code
        report.sensitive_domains = result.domains

        report.sections.clear()
        report.findings.clear()
        report.improved_version = None
        db.flush()
        for i, s in enumerate(result.sections):
            report.sections.append(
                CodeSection(
                    order_index=i,
                    start_line=s["start_line"],
                    end_line=s["end_line"],
                    title=s["title"][:200],
                    explanation=s["explanation"],
                )
            )
        for i, f in enumerate(result.findings):
            report.findings.append(
                Finding(
                    public_key=f.public_key,
                    category=f.category,
                    title=f.title[:200],
                    description=f.description,
                    evidence=f.evidence or None,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    severity=f.severity,
                    confidence=f.confidence,
                    confidence_reason=f.confidence_reason,
                    cwe_id=f.cwe_id,
                    owasp_category=f.owasp_category,
                    source=f.source,
                    static_tool=(f.static_tool or None) and f.static_tool[:30],
                    static_rule_id=(f.static_rule_id or None) and f.static_rule_id[:200],
                    recommendation=f.recommendation,
                    ai_assessment=f.ai_assessment,
                    order_index=i,
                )
            )
        if result.improved_code is not None:
            report.improved_version = ImprovedVersion(
                improved_code=result.improved_code, change_reasons=result.changes
            )

        # Consent (8.20): registered users' code is kept only when they agreed.
        sub = db.get(Submission, report.submission_id)
        if job.is_registered and not job.store_code:
            sub.code_text = None

        report.status = "completed"
        report.stage = "completed"
        report.error_message = None
        report.completed_at = utcnow()
        report.processing_time_ms = int((time.monotonic() - started) * 1000)
        db.commit()


def run_job(public_id: str) -> None:
    """Background job entry point: never raises; failures are recorded on the report."""
    started = time.monotonic()
    try:
        job = _load(public_id)
        if job is None:
            return
        set_stage(public_id, "validating", status="running", started_at=utcnow())

        def progress(stage: str) -> None:
            set_stage(public_id, stage)

        result = analyse(job, progress)
        set_stage(public_id, "saving")
        save(job, result, started)
        log.info(
            "analysis completed",
            extra={
                "event": "analysis_completed",
                "public_id": public_id,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "status": ("completed" if result.ai_available else f"fallback:{result.ai_reason}"),
            },
        )
    except Exception:
        log.exception(
            "analysis failed",
            extra={"event": "analysis_failed", "public_id": public_id},
        )
        try:
            set_stage(public_id, "completed", status="failed", error_message=FAILED_MESSAGE)
        except Exception:  # noqa: BLE001
            log.exception("could not mark analysis as failed", extra={"public_id": public_id})


def run_pipeline_for_code(code: str, language_choice: str = "auto", filename: str | None = None) -> dict:
    """Run the full pipeline in-process (benchmark and live tests): creates a guest analysis and returns
    the report JSON. Uses the same code path as the API."""
    from app.services.report_service import build_report

    with SessionLocal() as db:
        values = settings_service.get(db)
        v = validation.validate(code, language_choice, filename, values["max_lines"], values["max_chars"])
        lang = language.resolve(v.code, v.language, v.filename)
        sub = Submission(
            user_id=None,
            language=lang.language,
            language_source=lang.source,
            filename=v.filename,
            code_text=v.code,
            code_hash=hashlib.sha256(v.code.encode("utf-8")).hexdigest(),
            line_count=v.line_count,
            char_count=v.char_count,
            store_code=True,
        )
        db.add(sub)
        db.flush()
        report = AnalysisReport(
            submission_id=sub.submission_id,
            status="queued",
            stage="validating",
            llm_provider=get_settings().LLM_PROVIDER,
            prompt_version=get_settings().PROMPT_VERSION,
            llm_requests=0,
            redaction_count=0,
        )
        db.add(report)
        db.commit()
        public_id = report.public_id
    run_job(public_id)
    with SessionLocal() as db:
        report = db.query(AnalysisReport).filter_by(public_id=public_id).one()
        if report.status != "completed":
            raise RuntimeError(report.error_message or "analysis failed")
        return build_report(db, report)
