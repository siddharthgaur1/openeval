from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TraceCreate(BaseModel):
    # Omit to use the caller's default (personal) project - see
    # services.organization_service.get_default_project.
    project_id: UUID | None = None
    name: str = "llm-call"
    model: str
    prompt: str
    response: str = ""
    latency_ms: float = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0
    tags: dict = {}
    error: str | None = None


class TraceOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    model: str
    prompt: str
    response: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    tags: dict
    error: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    score: int  # thumbs down/up as -1/1, or a 1-5 scale - caller's choice
    comment: str | None = None


class TraceExportRequest(BaseModel):
    trace_ids: list[UUID]
    dataset_name: str = "traces-export"


class TraceStats(BaseModel):
    count: int
    total_cost_usd: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
