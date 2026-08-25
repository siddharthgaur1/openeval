"""experiments table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("baseline_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_runs.id"), nullable=True),
        sa.Column("run_ids", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("experiments")
