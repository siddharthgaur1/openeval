from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.organization import Membership
from models.project import Project
from models.user import User
from schemas.organization import ProjectOut
from services.organization_service import get_default_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/default", response_model=ProjectOut)
def default_project(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The project the frontend/SDK use when nothing more specific is chosen -
    resolves to the caller's earliest project, provisioning one if they somehow
    have none (shouldn't happen post-registration, but is not fatal if it does).
    """
    project = get_default_project(db, current_user)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_my_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Every project across every organization the caller is a member of - for a
    project switcher UI.
    """
    org_ids = [m.organization_id for m in db.query(Membership).filter(Membership.user_id == current_user.id).all()]
    if not org_ids:
        return []
    return db.query(Project).filter(Project.organization_id.in_(org_ids)).order_by(Project.created_at).all()
