from sqlalchemy.orm import Session

from models.organization import Membership, Organization
from models.project import Project
from models.user import User


def provision_default_workspace(db: Session, user: User) -> Project:
    """Every user gets a personal Organization + default Project on registration,
    so single-user usage never requires explicit org/project setup (matches how
    e.g. GitHub gives you a personal account that behaves like an org of one).
    Does not commit - caller controls the transaction.
    """
    org = Organization(name=f"{user.email}'s Workspace")
    db.add(org)
    db.flush()

    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))

    project = Project(organization_id=org.id, name="default")
    db.add(project)
    db.flush()

    return project


def get_default_project(db: Session, user: User) -> Project:
    """The user's first project by membership creation order - used to resolve an
    omitted `project_id` on SDK/API calls that predate explicit project selection.
    """
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id)
        .order_by(Membership.created_at)
        .first()
    )
    if not membership:
        return provision_default_workspace(db, user)

    project = db.query(Project).filter(Project.organization_id == membership.organization_id).order_by(Project.created_at).first()
    if not project:
        # Defensive: a membership with no project under its org shouldn't happen via
        # our own code paths, but don't 500 on it - just provision one.
        project = Project(organization_id=membership.organization_id, name="default")
        db.add(project)
        db.flush()
    return project
