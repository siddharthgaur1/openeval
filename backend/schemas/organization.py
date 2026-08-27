from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from models.organization import ROLES


class OrganizationCreate(BaseModel):
    name: str


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    role: str  # caller's role in this org

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    trace_quota_per_month: int = 1_000_000
    eval_run_quota_per_month: int = 1_000


class ProjectOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    trace_quota_per_month: int
    eval_run_quota_per_month: int
    created_at: datetime

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"

    @field_validator("role")
    @classmethod
    def validate_role(cls, role: str) -> str:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return role


class MembershipOut(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    role: str

    class Config:
        from_attributes = True
