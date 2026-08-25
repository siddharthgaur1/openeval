from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ExperimentCreate(BaseModel):
    # Omit to use the caller's default project (or, if run_ids are given, the
    # first run's project - see api/experiments.py).
    project_id: UUID | None = None
    name: str
    run_ids: list[UUID] = []
    baseline_run_id: UUID | None = None
    notes: str | None = None


class ExperimentOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    baseline_run_id: UUID | None
    run_ids: list[UUID]
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SetBaselineRequest(BaseModel):
    run_id: UUID
