from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import decode_access_token, verify_api_key
from models.user import APIKey, User
from services.rate_limit import check_rate_limit

bearer_scheme = HTTPBearer(auto_error=False)

# Endpoints that mutate account/access-control state rather than project data -
# gated to "admin"-scoped keys (JWT logins are always full access, since they
# authenticate the human account owner directly, not a delegated key).
_ADMIN_ONLY_PREFIXES = ("/api/auth/api-keys",)


def _resolve_user(token: str, db: Session) -> tuple[User, str | None]:
    """Returns (user, api_key_scope). api_key_scope is None for JWT logins,
    which always carry the full access of the logged-in account."""
    if token.startswith("oe_"):
        prefix = token[:12]
        candidates = db.query(APIKey).filter(APIKey.prefix == prefix).all()
        for candidate in candidates:
            if verify_api_key(token, candidate.hashed_key):
                user = db.query(User).filter(User.id == candidate.user_id).first()
                if user:
                    return user, candidate.scope
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user, None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    # `token` query param exists only because browsers' native EventSource can't set
    # an Authorization header - used by the SSE endpoint. Every other route relies on
    # the Bearer header.
    token = credentials.credentials if credentials else token
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")

    user, api_key_scope = _resolve_user(token, db)

    if api_key_scope is not None:
        if request.method not in ("GET", "HEAD") and api_key_scope == "read":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This API key is read-only")
        if request.url.path.startswith(_ADMIN_ONLY_PREFIXES) and api_key_scope != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This action requires an admin-scoped API key")

    allowed, remaining = check_rate_limit(str(user.id), limit=settings.rate_limit_per_minute, window_seconds=60)
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")

    return user
