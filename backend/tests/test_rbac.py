from uuid import uuid4

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from api.rbac import check_quota, require_role
from models.organization import ROLE_RANK, ROLES


def test_role_rank_orders_owner_highest():
    assert ROLE_RANK["owner"] > ROLE_RANK["admin"] > ROLE_RANK["member"] > ROLE_RANK["viewer"]


def test_all_roles_ranked():
    assert set(ROLE_RANK.keys()) == set(ROLES)


def test_require_role_rejects_project_not_found():
    dependency = require_role("member")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        dependency(project_id=uuid4(), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 404


def test_require_role_rejects_non_member():
    dependency = require_role("member")
    db = MagicMock()
    project = MagicMock(organization_id=uuid4())
    # First query -> project lookup; second query -> membership lookup (None)
    db.query.return_value.filter.return_value.first.side_effect = [project, None]

    with pytest.raises(HTTPException) as exc_info:
        dependency(project_id=uuid4(), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 403


def test_require_role_rejects_insufficient_role():
    dependency = require_role("admin")
    db = MagicMock()
    project = MagicMock(organization_id=uuid4())
    membership = MagicMock(role="viewer")
    db.query.return_value.filter.return_value.first.side_effect = [project, membership]

    with pytest.raises(HTTPException) as exc_info:
        dependency(project_id=uuid4(), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 403


def test_require_role_allows_sufficient_role():
    dependency = require_role("member")
    db = MagicMock()
    project = MagicMock(organization_id=uuid4())
    membership = MagicMock(role="admin")
    db.query.return_value.filter.return_value.first.side_effect = [project, membership]

    result = dependency(project_id=uuid4(), db=db, current_user=MagicMock())
    assert result is project


def test_check_quota_allows_under_limit():
    db = MagicMock()
    project = MagicMock(id=uuid4(), trace_quota_per_month=100)
    db.query.return_value.filter.return_value.count.return_value = 99
    check_quota(db, project, "trace")  # should not raise


def test_check_quota_rejects_at_limit():
    db = MagicMock()
    project = MagicMock(id=uuid4(), eval_run_quota_per_month=10)
    db.query.return_value.filter.return_value.count.return_value = 10
    with pytest.raises(HTTPException) as exc_info:
        check_quota(db, project, "eval_run")
    assert exc_info.value.status_code == 429
