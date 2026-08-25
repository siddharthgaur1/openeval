from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from models.webhook import WEBHOOK_EVENTS


class WebhookCreate(BaseModel):
    project_id: UUID | None = None  # omit to use the caller's default project
    url: str
    events: list[str]
    secret: str | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: list[str]) -> list[str]:
        unknown = set(events) - set(WEBHOOK_EVENTS)
        if unknown:
            raise ValueError(f"Unknown event(s): {unknown}. Valid: {WEBHOOK_EVENTS}")
        return events


class WebhookOut(BaseModel):
    id: UUID
    project_id: UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
