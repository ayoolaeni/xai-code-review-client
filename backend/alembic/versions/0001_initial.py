"""Initial schema (Section 6).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("store_code_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "submissions",
        sa.Column("submission_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("language_source", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("code_text", sa.Text(), nullable=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("store_code", sa.Boolean(), nullable=False),
        sa.Column("client_ip_hash", sa.String(64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"])

    op.create_table(
        "analysis_reports",
        sa.Column("report_id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("purpose_summary", sa.Text(), nullable=True),
        sa.Column("overall_risk_level", sa.String(10), nullable=True),
        sa.Column("overall_confidence", sa.String(10), nullable=True),
        sa.Column("human_review_advised", sa.Boolean(), nullable=True),
        sa.Column("review_reasons", sa.JSON(), nullable=True),
        sa.Column("limitations_note", sa.JSON(), nullable=True),
        sa.Column("ai_explanation_available", sa.Boolean(), nullable=True),
        sa.Column("ai_unavailable_reason", sa.String(30), nullable=True),
        sa.Column("ai_unavailable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("llm_provider", sa.String(20), nullable=True),
        sa.Column("llm_requests", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("tools_run", sa.JSON(), nullable=True),
        sa.Column("consistency", sa.JSON(), nullable=True),
        sa.Column("improved_code_check", sa.JSON(), nullable=True),
        sa.Column("redaction_count", sa.Integer(), nullable=False),
        sa.Column("redaction_by_type", sa.JSON(), nullable=True),
        sa.Column("redacted_code", sa.Text(), nullable=True),
        sa.Column("sensitive_domains", sa.JSON(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_reports_public_id", "analysis_reports", ["public_id"], unique=True)

    op.create_table(
        "code_sections",
        sa.Column("section_id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.CheckConstraint("start_line >= 1", name="ck_section_start"),
        sa.CheckConstraint("end_line >= start_line", name="ck_section_range"),
    )
    op.create_index("ix_code_sections_report_id", "code_sections", ["report_id"])

    op.create_table(
        "findings",
        sa.Column("finding_id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("public_key", sa.String(10), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("confidence_reason", sa.Text(), nullable=False),
        sa.Column("cwe_id", sa.String(15), nullable=True),
        sa.Column("owasp_category", sa.String(60), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("static_tool", sa.String(30), nullable=True),
        sa.Column("static_rule_id", sa.String(200), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("ai_assessment", sa.String(25), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
    )
    op.create_index("ix_findings_report_id", "findings", ["report_id"])

    op.create_table(
        "improved_versions",
        sa.Column("version_id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("improved_code", sa.Text(), nullable=False),
        sa.Column("change_reasons", sa.JSON(), nullable=False),
    )

    op.create_table(
        "feedback",
        sa.Column("feedback_id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("analysis_reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True),
        sa.Column("feedback_token", sa.String(36), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("was_helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
        sa.UniqueConstraint("report_id", "user_id", name="uq_feedback_report_user"),
        sa.UniqueConstraint("report_id", "feedback_token", name="uq_feedback_report_token"),
    )
    op.create_index("ix_feedback_report_id", "feedback", ["report_id"])

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_by", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
        ),
    )

    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    for table in (
        "llm_usage",
        "system_settings",
        "feedback",
        "improved_versions",
        "findings",
        "code_sections",
        "analysis_reports",
        "submissions",
        "users",
    ):
        op.drop_table(table)
