"""annotation queue + annotations

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-25

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "annotation_queue_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("traces.id"), nullable=False, index=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rubric", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("annotation_queue_items.id"), nullable=False, index=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("traces.id"), nullable=False, index=True),
        sa.Column("annotator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("scores", sa.JSON, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("annotations")
    op.drop_table("annotation_queue_items")
