"""Owner vs admin separation and member role-change/removal rules.

Endpoint tests call the route functions directly with a mocked Session, like
tests/test_rbac.py does for require_role.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api import organizations as orgs_api
from schemas.organization import InviteMemberRequest, UpdateMemberRoleRequest
from services.organization_service import check_membership_change


def _db(*first_results, owners=1):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = list(first_results)
    db.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [object()] * owners
    db.refresh.side_effect = lambda m: setattr(m, "id", m.id or uuid4())
    return db


def _m(role, user_id=None):
    return SimpleNamespace(id=uuid4(), user_id=user_id or uuid4(), role=role)


# --- pure rule ---

@pytest.mark.parametrize(
    "actor,target,new,owners,is_self,err",
    [
        ("admin", None, "owner", 1, False, PermissionError),  # admin invites owner
        ("admin", "member", "owner", 1, False, PermissionError),  # admin promotes to owner
        ("admin", "owner", "member", 2, False, PermissionError),  # admin demotes owner
        ("admin", "owner", None, 2, False, PermissionError),  # admin removes owner
        ("admin", "admin", "member", 1, False, PermissionError),  # admin demotes peer admin
        ("member", "viewer", "member", 1, False, PermissionError),  # member changes roles
        ("viewer", "member", None, 1, False, PermissionError),  # viewer removes someone
        ("owner", "owner", "admin", 1, True, ValueError),  # last owner demotes self
        ("owner", "owner", None, 1, True, ValueError),  # last owner leaves
        ("owner", "owner", None, 1, False, ValueError),  # remove last owner
    ],
)
def test_check_membership_change_rejects(actor, target, new, owners, is_self, err):
    with pytest.raises(err):
        check_membership_change(actor, target, new, owners, is_self)


@pytest.mark.parametrize(
    "actor,target,new,owners,is_self",
    [
        ("owner", None, "owner", 1, False),  # owner invites owner
        ("owner", "member", "owner", 1, False),  # owner promotes to owner
        ("owner", "owner", "admin", 2, False),  # owner demotes another owner (not last)
        ("owner", "owner", None, 2, True),  # owner leaves when another owner exists
        ("admin", None, "admin", 1, False),  # admin invites admin (unchanged behaviour)
        ("admin", "viewer", "member", 1, False),  # admin manages members/viewers
        ("admin", "member", None, 1, False),
        ("admin", "admin", "member", 1, True),  # admin demotes self
        ("viewer", "viewer", None, 1, True),  # anyone may leave
    ],
)
def test_check_membership_change_allows(actor, target, new, owners, is_self):
    check_membership_change(actor, target, new, owners, is_self)


# --- endpoints ---

def test_admin_cannot_invite_owner():
    db = _db(_m("admin"), SimpleNamespace(id=uuid4(), email="x@example.com"), None)
    with pytest.raises(HTTPException) as exc:
        orgs_api.invite_member(uuid4(), InviteMemberRequest(email="x@example.com", role="owner"), db=db, current_user=MagicMock())
    assert exc.value.status_code == 403
    db.commit.assert_not_called()


def test_owner_can_invite_owner():
    db = _db(_m("owner"), SimpleNamespace(id=uuid4(), email="x@example.com"), None)
    out = orgs_api.invite_member(uuid4(), InviteMemberRequest(email="x@example.com", role="owner"), db=db, current_user=MagicMock())
    assert out.role == "owner"


def test_admin_cannot_remove_owner():
    db = _db(_m("admin"), _m("owner"), owners=2)
    with pytest.raises(HTTPException) as exc:
        orgs_api.remove_member(uuid4(), uuid4(), db=db, current_user=MagicMock())
    assert exc.value.status_code == 403
    db.delete.assert_not_called()


def test_last_owner_removal_blocked():
    me = uuid4()
    db = _db(_m("owner", me), _m("owner", me), owners=1)
    with pytest.raises(HTTPException) as exc:
        orgs_api.remove_member(uuid4(), uuid4(), db=db, current_user=SimpleNamespace(id=me))
    assert exc.value.status_code == 409
    db.delete.assert_not_called()


def test_member_cannot_change_roles():
    target = _m("viewer")
    db = _db(_m("member"), target)
    with pytest.raises(HTTPException) as exc:
        orgs_api.update_member_role(uuid4(), uuid4(), UpdateMemberRoleRequest(role="admin"), db=db, current_user=MagicMock())
    assert exc.value.status_code == 403
    assert target.role == "viewer"


def test_update_unknown_membership_404():
    db = _db(_m("owner"), None)
    with pytest.raises(HTTPException) as exc:
        orgs_api.update_member_role(uuid4(), uuid4(), UpdateMemberRoleRequest(role="admin"), db=db, current_user=MagicMock())
    assert exc.value.status_code == 404


def test_owner_promotes_member_to_owner():
    target = _m("member")
    db = _db(_m("owner"), target)
    db.query.return_value.filter.return_value.scalar.return_value = "t@example.com"
    out = orgs_api.update_member_role(uuid4(), target.id, UpdateMemberRoleRequest(role="owner"), db=db, current_user=MagicMock())
    assert target.role == "owner" and out.role == "owner"
    db.commit.assert_called_once()


def test_admin_removes_member():
    target = _m("member")
    db = _db(_m("admin"), target)
    orgs_api.remove_member(uuid4(), target.id, db=db, current_user=MagicMock())
    db.delete.assert_called_once_with(target)
    db.commit.assert_called_once()


def test_update_rejects_unknown_role():
    with pytest.raises(ValueError):
        UpdateMemberRoleRequest(role="superuser")
