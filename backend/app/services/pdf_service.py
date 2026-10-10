"""PDF export of a report with Jinja2 + WeasyPrint (Section 10, FR12)."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.errors import AppError

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))

SOURCE_TEXT = {
    "both": "static analysis + AI",
    "static": "static analysis only",
    "llm": "AI only",
}
ASSESSMENT_TEXT = {
    "agree": "agrees this is a real problem",
    "likely_false_positive": "thinks this may be a false positive",
    "not_reviewed": "did not review it",
}
DOMAIN_LABELS = {
    "authentication": "Authentication",
    "cryptography": "Cryptography",
    "payments": "Payments",
    "personal_data": "Personal data",
}


def render_html(report: dict) -> str:
    code = report["submission"]["original_code"] or report["submission"]["redacted_code"] or ""
    code_lines = code.split("\n")
    improved = report["improved"]["improved_code"] or ""
    improved_lines = improved.split("\n") if improved else []
    ms = report.get("processing_time_ms")
    return _env.get_template("report_pdf.html").render(
        r=report,
        short_id=report["public_id"][:8],
        generated_at=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M"),
        code_lines=code_lines,
        width=len(str(len(code_lines))),
        improved_lines=improved_lines,
        improved_width=len(str(max(1, len(improved_lines)))),
        source_text=SOURCE_TEXT,
        assessment_text=ASSESSMENT_TEXT,
        domains=", ".join(DOMAIN_LABELS.get(d, d) for d in report["overview"]["sensitive_domains"]),
        processing=f"{ms / 1000:.1f} s" if ms else "—",
    )


def render_pdf(report: dict) -> bytes:
    try:
        from weasyprint import HTML  # imported lazily: needs the Pango system libraries
    except (ImportError, OSError) as e:
        log.error("WeasyPrint is not usable on this server: %s", e)
        raise AppError(
            503,
            "PDF_UNAVAILABLE",
            "PDF export is not available on this server (the PDF library is not installed). "
            "Use the Docker image, which includes it.",
        ) from e
    # The template is self-contained (no external resources); user text is auto-escaped by Jinja2.
    return HTML(string=render_html(report), base_url=str(TEMPLATES)).write_pdf()


def is_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True
