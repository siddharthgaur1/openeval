from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.organization import ROLE_RANK, Membership
from models.project import Project
from models.user import User


def get_membership(db: Session, user_id, organization_id) -> Membership | None:
    return db.query(Membership).filter(Membership.organization_id == organization_id, Membership.user_id == user_id).first()


def check_project_role(db: Session, user_id, project_id, min_role: str) -> Project:
    """Verify the caller has at least `min_role` in `project_id`'s organization and
    return the Project row. Raises 404 if the project doesn't exist, 403 if the
    caller isn't a member or is under-ranked. Roles rank owner > admin > member > viewer.
    Callable directly (for POST bodies, where project_id isn't a path/query param
    FastAPI can inject) or wrapped by `require_role` below (for GET routes).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    membership = get_membership(db, user_id, project.organization_id)
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this project's organization")

    if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{min_role}' or higher, you have '{membership.role}'")

    return project


def require_role(min_role: str):
    """FastAPI dependency factory for routes where `project_id` is a query (or path)
    param FastAPI can inject directly - typically GET/list routes. For POST routes
    where project_id lives in the request body, call check_project_role(...) manually
    instead (FastAPI dependencies can't read a sibling body param).
    """

    def dependency(
        project_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> Project:
        return check_project_role(db, current_user.id, project_id, min_role)

    return dependency
