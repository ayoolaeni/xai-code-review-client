"""Pydantic models for the LLM's JSON replies (Section 8.8, NFR4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.pipeline.taxonomy import normalise_cwe

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Category = Literal["security", "reliability", "performance", "maintainability"]
Domain = Literal["authentication", "cryptography", "payments", "personal_data"]


def _norm_cwe(v: object) -> str | None:
    # accept "89", "CWE89", "cwe-89" → "CWE-89"; anything else → None
    return normalise_cwe(v)


class Section(BaseModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1)


class LLMFinding(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Category
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    description: str = Field(min_length=1)
    evidence: str = ""
    recommendation: str = Field(min_length=1)
    severity_suggested: Severity
    cwe_id: str | None = None
    model_uncertain: bool = False
    related_static_ids: list[str] = []

    @field_validator("cwe_id", mode="before")
    @classmethod
    def norm_cwe(cls, v):
        return _norm_cwe(v)


class StaticAssessment(BaseModel):
    static_id: str
    verdict: Literal["agree", "likely_false_positive"]
    reason: str


class Change(BaseModel):
    number: int = Field(ge=1)
    description: str
    reason: str
    related_findings: list[int] = []
    original_lines: list[int] | None = None  # [start, end] or null


class ExplanationOutput(BaseModel):
    purpose_summary: str = Field(min_length=10)
    breakdown: list[Section] = Field(min_length=1)
    findings: list[LLMFinding] = []
    static_assessment: list[StaticAssessment] = []
    improved_code: str = Field(min_length=1)
    changes: list[Change] = []
    sensitive_domains: list[Domain] = []
    limitations: list[str] = []


class RiskOnlyFinding(BaseModel):
    title: str
    category: Category
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    severity_suggested: Severity
    cwe_id: str | None = None
    model_uncertain: bool = False

    @field_validator("cwe_id", mode="before")
    @classmethod
    def norm_cwe(cls, v):
        return _norm_cwe(v)


class RiskOnlyOutput(BaseModel):
    findings: list[RiskOnlyFinding] = []
