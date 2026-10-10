"""SQLAlchemy models (Section 6). Columns marked (ops) in the spec are listed in docs/DECISIONS.md."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    store_code_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list[Submission]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True, index=True
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    language_source: Mapped[str] = mapped_column(String(10), nullable=False, default="auto")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SECURITY: never execute user code — stored as text only.
    code_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    store_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # (ops) consent flag
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )

    user: Mapped[User | None] = relationship(back_populates="submissions")
    report: Mapped[AnalysisReport | None] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="validating")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    overall_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    human_review_advised: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    review_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    limitations_note: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_explanation_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_unavailable_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ai_unavailable_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    llm_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tools_run: Mapped[list | None] = mapped_column(JSON, nullable=True)
    consistency: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    improved_code_check: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    redaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redaction_by_type: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # (ops)
    redacted_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitive_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # (ops)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="report")
    sections: Mapped[list[CodeSection]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CodeSection.order_index",
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Finding.order_index",
    )
    improved_version: Mapped[ImprovedVersion | None] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )


class CodeSection(Base):
    __tablename__ = "code_sections"

    section_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    report: Mapped[AnalysisReport] = relationship(back_populates="sections")

    __table_args__ = (
        CheckConstraint("start_line >= 1", name="ck_section_start"),
        CheckConstraint("end_line >= start_line", name="ck_section_range"),
    )


class Finding(Base):
    __tablename__ = "findings"

    finding_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_key: Mapped[str] = mapped_column(String(10), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence_reason: Mapped[str] = mapped_column(Text, nullable=False)
    cwe_id: Mapped[str | None] = mapped_column(String(15), nullable=True)
    owasp_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    static_tool: Mapped[str | None] = mapped_column(String(30), nullable=True)
    static_rule_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    ai_assessment: Mapped[str | None] = mapped_column(String(25), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    report: Mapped[AnalysisReport] = relationship(back_populates="findings")


class ImprovedVersion(Base):
    __tablename__ = "improved_versions"

    version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    improved_code: Mapped[str] = mapped_column(Text, nullable=False)
    change_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    report: Mapped[AnalysisReport] = relationship(back_populates="improved_version")


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    feedback_token: Mapped[str | None] = mapped_column(String(36), nullable=True)  # (ops) guests
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    was_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    report: Mapped[AnalysisReport] = relationship(back_populates="feedback")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
        UniqueConstraint("report_id", "user_id", name="uq_feedback_report_user"),
        UniqueConstraint("report_id", "feedback_token", name="uq_feedback_report_token"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
