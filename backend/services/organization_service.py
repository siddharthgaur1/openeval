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


def check_membership_change(actor_role: str, target_role: str | None, new_role: str | None, owner_count: int, is_self: bool) -> None:
    """Authorize inviting (target_role=None), re-roling, or removing (new_role=None) a
    member. Raises PermissionError (-> 403) or ValueError (-> 409, last owner).

    - Anyone may remove themselves (leave).
    - Otherwise the actor must be admin or owner.
    - Only an owner can grant or revoke the owner role.
    - An admin cannot demote or remove another admin (only themselves).
    - The last owner can never be demoted or removed - the org would be orphaned.
    """
    if not (new_role is None and is_self):
        if actor_role not in ("owner", "admin"):
            raise PermissionError("Requires role 'admin' or higher")
        if "owner" in (target_role, new_role) and actor_role != "owner":
            raise PermissionError("Only an owner can grant or revoke the owner role")
        if actor_role == "admin" and target_role == "admin" and not is_self:
            raise PermissionError("Admins cannot change or remove another admin")
    if target_role == "owner" and new_role != "owner" and owner_count <= 1:
        raise ValueError("Cannot demote or remove the last owner - make someone else an owner first")
