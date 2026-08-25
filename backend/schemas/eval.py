from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EvalRunCreate(BaseModel):
    name: str = "eval-run"
    dataset_id: UUID
    prompt_template_id: UUID | None = None
    target_model: str
    judge_model: str | None = None
    metrics: list[str] = ["exact_match", "f1", "answer_relevance", "faithfulness", "hallucination"]


class EvalResultOut(BaseModel):
    id: UUID
    dataset_row_id: UUID
    output: str
    scores: dict
    latency_ms: float
    cost_usd: float

    class Config:
        from_attributes = True


class EvalRunOut(BaseModel):
    id: UUID
    name: str
    dataset_id: UUID
    target_model: str
    judge_model: str
    metrics: list[str]
    status: str
    total_rows: int
    completed_rows: int
    failed_rows: int
    summary: dict
    error: str | None
    created_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True


class EvalRunDetail(EvalRunOut):
    results: list[EvalResultOut] = []


class CompareRequest(BaseModel):
    run_ids: list[UUID]
    regression_threshold: float = 0.05
