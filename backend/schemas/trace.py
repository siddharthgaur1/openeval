from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TraceCreate(BaseModel):
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


class TraceOut(TraceCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class TraceStats(BaseModel):
    count: int
    total_cost_usd: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
