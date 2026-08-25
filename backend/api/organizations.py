from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import get_membership
from core.database import get_db
from models.organization import Membership, Organization
from models.project import Project
from models.user import User
from schemas.organization import (
    InviteMemberRequest,
    MembershipOut,
    OrganizationCreate,
    OrganizationOut,
    ProjectCreate,
    ProjectOut,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org = Organization(name=payload.name)
    db.add(org)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=current_user.id, role="owner"))
    db.commit()
    db.refresh(org)
    return OrganizationOut(id=org.id, name=org.name, created_at=org.created_at, role="owner")


@router.get("", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    orgs = {m.organization_id: m.role for m in memberships}
    rows = db.query(Organization).filter(Organization.id.in_(orgs.keys())).all()
    return [OrganizationOut(id=o.id, name=o.name, created_at=o.created_at, role=orgs[o.id]) for o in rows]


@router.post("/{organization_id}/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
def invite_member(organization_id: UUID, payload: InviteMemberRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    caller_membership = get_membership(db, current_user.id, organization_id)
    if not caller_membership or caller_membership.role not in ("owner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires role 'admin' or higher")

    invitee = db.query(User).filter(User.email == payload.email).first()
    if not invitee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email - they must register first")

    if get_membership(db, invitee.id, organization_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member")

    membership = Membership(organization_id=organization_id, user_id=invitee.id, role=payload.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.get("/{organization_id}/members", response_model=list[MembershipOut])
def list_members(organization_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not get_membership(db, current_user.id, organization_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    return db.query(Membership).filter(Membership.organization_id == organization_id).all()


@router.post("/{organization_id}/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(organization_id: UUID, payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = get_membership(db, current_user.id, organization_id)
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires role 'admin' or higher")

    project = Project(organization_id=organization_id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{organization_id}/projects", response_model=list[ProjectOut])
def list_projects(organization_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not get_membership(db, current_user.id, organization_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    return db.query(Project).filter(Project.organization_id == organization_id).all()
