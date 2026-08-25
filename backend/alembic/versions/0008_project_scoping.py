"""Scope traces/datasets/prompt_templates/eval_runs/experiments/webhooks to a
project instead of directly to a user - the multi-tenancy retrofit.

Adds project_id nullable, backfills a personal Organization + "default" Project
for every existing user who doesn't already have one (matching
services.organization_service.provision_default_workspace), points their
existing rows at it, then makes the column NOT NULL. Safe to run against a
database with existing production data - not just a fresh install.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26

"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLES = ["traces", "datasets", "prompt_templates", "eval_runs", "experiments", "webhooks"]


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))

    _backfill_default_projects()

    for table in TABLES:
        op.alter_column(table, "project_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_project_id", table, "projects", ["project_id"], ["id"])
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def _backfill_default_projects():
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # Users who already have a membership (e.g. created via the API after 0006)
    # keep using their earliest project - only users with zero memberships need
    # a workspace provisioned here.
    users_without_membership = conn.execute(
        sa.text("""
            SELECT u.id, u.email FROM users u
            LEFT JOIN memberships m ON m.user_id = u.id
            WHERE m.id IS NULL
        """)
    ).fetchall()

    for user_id, email in users_without_membership:
        org_id = uuid.uuid4()
        conn.execute(
            sa.text("INSERT INTO organizations (id, name, created_at) VALUES (:id, :name, :created_at)"),
            {"id": org_id, "name": f"{email}'s Workspace", "created_at": now},
        )
        conn.execute(
            sa.text("INSERT INTO memberships (id, organization_id, user_id, role, created_at) VALUES (:id, :org_id, :user_id, 'owner', :created_at)"),
            {"id": uuid.uuid4(), "org_id": org_id, "user_id": user_id, "created_at": now},
        )
        project_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, trace_quota_per_month, eval_run_quota_per_month, created_at) "
                "VALUES (:id, :org_id, 'default', 1000000, 1000, :created_at)"
            ),
            {"id": project_id, "org_id": org_id, "created_at": now},
        )
        _backfill_user_rows(conn, user_id, project_id)

    # Users who have a membership but rows still missing project_id (created
    # between 0006 shipping and this migration) - point them at their earliest project.
    users_with_membership = conn.execute(sa.text("SELECT DISTINCT user_id FROM memberships")).fetchall()
    for (user_id,) in users_with_membership:
        default_project = conn.execute(
            sa.text("""
                SELECT p.id FROM projects p
                JOIN memberships m ON m.organization_id = p.organization_id
                WHERE m.user_id = :user_id
                ORDER BY p.created_at
                LIMIT 1
            """),
            {"user_id": user_id},
        ).fetchone()
        if default_project:
            _backfill_user_rows(conn, user_id, default_project[0], only_missing=True)


def _backfill_user_rows(conn, user_id, project_id, only_missing: bool = False):
    missing_clause = " AND project_id IS NULL" if only_missing else ""
    for table in TABLES:
        conn.execute(
            sa.text(f"UPDATE {table} SET project_id = :project_id WHERE user_id = :user_id{missing_clause}"),
            {"project_id": project_id, "user_id": user_id},
        )


def downgrade():
    for table in TABLES:
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_constraint(f"fk_{table}_project_id", table, type_="foreignkey")
        op.drop_column(table, "project_id")
