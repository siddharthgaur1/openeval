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


def require_role(min_role: str):
    """FastAPI dependency factory: resolves `project_id` from the path, checks the
    caller has at least `min_role` in that project's organization, and returns
    the Project row. Roles rank owner > admin > member > viewer.
    """

    def dependency(
        project_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> Project:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

        membership = get_membership(db, current_user.id, project.organization_id)
        if not membership:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this project's organization")

        if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{min_role}' or higher, you have '{membership.role}'")

        return project

    return dependency
