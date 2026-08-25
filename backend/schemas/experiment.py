from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ExperimentCreate(BaseModel):
    name: str
    run_ids: list[UUID] = []
    baseline_run_id: UUID | None = None
    notes: str | None = None


class ExperimentOut(BaseModel):
    id: UUID
    name: str
    baseline_run_id: UUID | None
    run_ids: list[UUID]
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SetBaselineRequest(BaseModel):
    run_id: UUID
