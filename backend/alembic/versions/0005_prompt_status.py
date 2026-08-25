"""prompt template status (draft/staging/production)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-25

"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prompt_templates", sa.Column("status", sa.String, nullable=False, server_default="draft"))


def downgrade():
    op.drop_column("prompt_templates", "status")
