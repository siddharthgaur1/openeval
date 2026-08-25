"""eval run row-level progress + failure tracking

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("eval_runs", sa.Column("total_rows", sa.Integer, nullable=False, server_default="0"))
    op.add_column("eval_runs", sa.Column("completed_rows", sa.Integer, nullable=False, server_default="0"))
    op.add_column("eval_runs", sa.Column("failed_rows", sa.Integer, nullable=False, server_default="0"))
    op.add_column("eval_results", sa.Column("error", sa.Text, nullable=True))


def downgrade():
    op.drop_column("eval_results", "error")
    op.drop_column("eval_runs", "failed_rows")
    op.drop_column("eval_runs", "completed_rows")
    op.drop_column("eval_runs", "total_rows")
