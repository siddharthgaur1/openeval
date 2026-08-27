from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.deps import get_current_user
from models.user import APIKey, User


def _request(method="GET", path="/api/traces"):
    req = MagicMock()
    req.method = method
    req.url.path = path
    return req


def _db_with_api_key(scope: str):
    user = User(id=uuid4(), email="u@example.com", hashed_password="x")
    key = APIKey(id=uuid4(), user_id=user.id, name="k", hashed_key="h", prefix="oe_abcdefghijk", scope=scope)

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is APIKey:
            q.filter.return_value.all.return_value = [key]
        elif model is User:
            q.filter.return_value.first.return_value = user
        return q

    db.query.side_effect = query_side_effect
    return db, user


@pytest.fixture(autouse=True)
def _stub_key_verification_and_rate_limit(monkeypatch):
    monkeypatch.setattr("api.deps.verify_api_key", lambda token, hashed: True)
    monkeypatch.setattr("api.deps.check_rate_limit", lambda *a, **k: (True, 0))


def _credentials():
    return MagicMock(credentials="oe_abcdefghijklmnopqrstuvwxyz")


def test_read_scoped_key_allows_get():
    db, user = _db_with_api_key("read")
    result = get_current_user(request=_request("GET", "/api/traces"), credentials=_credentials(), token=None, db=db)
    assert result.id == user.id


def test_read_scoped_key_rejects_post():
    db, _ = _db_with_api_key("read")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request=_request("POST", "/api/traces"), credentials=_credentials(), token=None, db=db)
    assert exc_info.value.status_code == 403


def test_write_scoped_key_rejects_admin_only_route():
    db, _ = _db_with_api_key("write")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request=_request("POST", "/api/auth/api-keys"), credentials=_credentials(), token=None, db=db)
    assert exc_info.value.status_code == 403


def test_write_scoped_key_allows_trace_post():
    db, user = _db_with_api_key("write")
    result = get_current_user(request=_request("POST", "/api/traces"), credentials=_credentials(), token=None, db=db)
    assert result.id == user.id


def test_admin_scoped_key_allows_admin_only_route():
    db, user = _db_with_api_key("admin")
    result = get_current_user(request=_request("POST", "/api/auth/api-keys"), credentials=_credentials(), token=None, db=db)
    assert result.id == user.id
