"""Add eval_results.score_details - evaluators can now return a ScoreResult
carrying reasoning/evidence alongside the score, and this is where that lands.

Nullable with no server default: rows written before this column existed read
back as NULL, which the API exposes as `score_details: null`.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-09

"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("eval_results", sa.Column("score_details", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("eval_results", "score_details")
