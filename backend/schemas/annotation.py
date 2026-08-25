from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AssignAnnotationRequest(BaseModel):
    trace_id: UUID
    assigned_to_user_id: UUID
    rubric: dict = {}  # e.g. {"type": "scale_1_5"} or {"type": "binary"} or {"criteria": ["coherence", "toxicity"]}


class AnnotationQueueItemOut(BaseModel):
    id: UUID
    trace_id: UUID
    assigned_to_user_id: UUID
    rubric: dict
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SubmitAnnotationRequest(BaseModel):
    scores: dict
    comment: str | None = None


class AnnotationOut(BaseModel):
    id: UUID
    queue_item_id: UUID
    trace_id: UUID
    annotator_id: UUID
    scores: dict
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class KappaRequest(BaseModel):
    criterion: str
    annotator_a_id: UUID
    annotator_b_id: UUID


class KappaResult(BaseModel):
    criterion: str
    n_shared_items: int
    kappa: float
