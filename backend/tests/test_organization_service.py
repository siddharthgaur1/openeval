from types import SimpleNamespace
from unittest.mock import MagicMock

from services.organization_service import get_default_project, provision_default_workspace


def test_provision_default_workspace_creates_org_membership_project():
    db = MagicMock()
    user = SimpleNamespace(id="user-1", email="a@example.com")

    project = provision_default_workspace(db, user)

    # organization, membership, project all added
    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert added_types == ["Organization", "Membership", "Project"]
    assert project.name == "default"


def test_get_default_project_returns_existing_when_membership_present():
    db = MagicMock()
    user = SimpleNamespace(id="user-1", email="a@example.com")
    membership = SimpleNamespace(organization_id="org-1")
    existing_project = SimpleNamespace(id="proj-1", organization_id="org-1")

    db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [membership, existing_project]

    result = get_default_project(db, user)

    assert result is existing_project
    db.add.assert_not_called()  # nothing new provisioned


def test_get_default_project_provisions_when_no_membership():
    db = MagicMock()
    user = SimpleNamespace(id="user-1", email="a@example.com")
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    project = get_default_project(db, user)

    added_types = [type(call.args[0]).__name__ for call in db.add.call_args_list]
    assert added_types == ["Organization", "Membership", "Project"]
    assert project.name == "default"
