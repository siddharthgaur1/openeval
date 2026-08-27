"""Add a scope column (read/write/admin) to api_keys and enforce it - previously
every API key had unrestricted access regardless of what scope the caller
requested at creation time (the field wasn't even stored).

Existing keys backfill to "write" (their previous de-facto behavior minus
admin-only actions), so this migration doesn't lock anyone out.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-27

"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_keys", sa.Column("scope", sa.String(), nullable=False, server_default="write"))
    op.alter_column("api_keys", "scope", server_default=None)


def downgrade():
    op.drop_column("api_keys", "scope")
