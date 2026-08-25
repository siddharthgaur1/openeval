"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-25

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("hashed_key", sa.String, nullable=False),
        sa.Column("prefix", sa.String, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "dataset_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False, index=True),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("expected_output", sa.Text, nullable=True),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=False),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("variables", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("prompt_template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prompt_templates.id"), nullable=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("target_model", sa.String, nullable=False),
        sa.Column("judge_model", sa.String, nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False, index=True),
        sa.Column("summary", sa.JSON, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "eval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("eval_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_runs.id"), nullable=False, index=True),
        sa.Column("dataset_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_rows.id"), nullable=False),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("scores", sa.JSON, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
    )


def downgrade():
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_table("prompt_templates")
    op.drop_table("dataset_rows")
    op.drop_table("datasets")
    op.drop_table("traces")
    op.drop_table("api_keys")
    op.drop_table("users")
