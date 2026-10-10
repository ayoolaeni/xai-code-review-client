"""Pydantic API schemas (Section 7) and the report contract (Section 9)."""

from __future__ import annotations

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SeverityT = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ConfidenceT = Literal["HIGH", "MEDIUM", "LOW"]


# ---------- Auth ----------
def _check_password(v: str) -> str:
    if not 8 <= len(v) <= 128:
        raise ValueError("Password must be 8 to 128 characters long.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain at least one letter and one digit.")
    return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str
    store_code_default: bool = False

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please enter your name.")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return _check_password(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UpdateMeIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    store_code_default: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    role: str
    store_code_default: bool
    created_at: dt.datetime


# ---------- Analyses ----------
class AnalysisCreate(BaseModel):
    code: str = Field(max_length=1_000_000)
    language: str = "auto"
    filename: str | None = Field(default=None, max_length=255)
    store_code: bool | None = None


class AnalysisCreated(BaseModel):
    public_id: str
    status: str


class AnalysisStatus(BaseModel):
    public_id: str
    status: str
    stage: str
    stage_label: str
    stage_index: int
    stage_count: int
    queue_position: int | None
    started_at: dt.datetime | None
    error_message: str | None


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    was_helpful: bool
    comment: str | None = Field(default=None, max_length=2000)
    feedback_token: str | None = Field(default=None, max_length=36)


class FeedbackOut(BaseModel):
    feedback_id: int
    feedback_token: str | None


# ---------- Admin ----------
class AdminUserPatch(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


# ---------- Report contract (Section 9) ----------
class CweOut(BaseModel):
    id: str
    name: str
    url: str


class SubmissionOut(BaseModel):
    language: str
    language_label: str
    language_source: str
    filename: str | None
    line_count: int
    code_stored: bool
    original_code: str | None
    redacted_code: str | None


class CountsOut(BaseModel):
    CRITICAL: int
    HIGH: int
    MEDIUM: int
    LOW: int
    total: int


class OverviewOut(BaseModel):
    purpose_summary: str
    overall_risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
    overall_confidence: ConfidenceT
    human_review_advised: bool
    review_reasons: list[str]
    no_review_message: str | None = None
    ai_explanation_available: bool
    ai_unavailable_reason: str | None
    ai_unavailable_message: str | None = None
    ai_unavailable_until: dt.datetime | None
    counts: CountsOut
    sensitive_domains: list[str]


class SectionOut(BaseModel):
    start_line: int
    end_line: int
    title: str
    explanation: str


class FindingOut(BaseModel):
    key: str
    category: Literal["security", "reliability", "performance", "maintainability"]
    title: str
    description: str
    evidence: str | None
    recommendation: str
    start_line: int
    end_line: int
    severity: SeverityT
    confidence: ConfidenceT
    confidence_reason: str
    cwe: CweOut | None
    owasp_category: str | None
    source: Literal["static", "llm", "both"]
    static_tool: str | None
    static_rule_id: str | None
    ai_assessment: str | None


class ChangeOut(BaseModel):
    number: int
    description: str
    reason: str
    related_findings: list[str]
    original_lines: list[int] | None


class ImprovedCheckOut(BaseModel):
    syntax_ok: bool | None
    syntax_message: str | None
    remaining_static_findings: int | None
    new_high_or_critical: int | None


class ImprovedOut(BaseModel):
    available: bool
    improved_code: str | None
    changes: list[ChangeOut]
    check: ImprovedCheckOut | None
    requires_acknowledgement: bool
    has_problems: bool = False


class ToolRunOut(BaseModel):
    tool: str
    version: str | None
    status: str
    findings_count: int
    message: str | None


class ConsistencyOut(BaseModel):
    enabled: bool
    run_b_ok: bool | None
    matched: int
    only_in_a: int
    only_in_b: int
    reason: str | None = None


class TransparencyOut(BaseModel):
    model_name: str | None
    llm_provider: str | None
    data_use_notice: str | None
    prompt_version: str | None
    llm_requests: int
    tools_run: list[ToolRunOut]
    redaction: dict
    consistency: ConsistencyOut
    checked: list[str]
    not_checked: list[str]
    limitations: list[str]
    code_executed: Literal[False]
    processing_time_ms: int | None
    code_storage_note: str | None


class FeedbackState(BaseModel):
    rating: int | None
    was_helpful: bool | None
    comment: str | None


class ReportOut(BaseModel):
    public_id: str
    status: Literal["completed"]
    created_at: dt.datetime
    completed_at: dt.datetime | None
    processing_time_ms: int | None
    expires_at: dt.datetime | None
    owner: Literal["guest", "user"]
    submission: SubmissionOut
    overview: OverviewOut
    breakdown: list[SectionOut]
    findings: list[FindingOut]
    improved: ImprovedOut
    transparency: TransparencyOut
    feedback: FeedbackState
