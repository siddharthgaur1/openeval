from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PromptTemplateCreate(BaseModel):
    name: str
    template: str
    variables: list[str] = []


class PromptTemplateOut(BaseModel):
    id: UUID
    name: str
    version: int
    template: str
    variables: list[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PlaygroundRequest(BaseModel):
    model: str
    variables: dict[str, str] = {}


class PlaygroundResult(BaseModel):
    rendered_prompt: str
    output: str
    latency_ms: float
    cost_usd: float
