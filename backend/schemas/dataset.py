from uuid import UUID

from pydantic import BaseModel, field_validator


class DatasetRowIn(BaseModel):
    input: str
    expected_output: str | None = None
    context: str | None = None
    tags: dict = {}


class DatasetRowOut(DatasetRowIn):
    id: UUID

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    project_id: UUID | None = None  # omit to use the caller's default project
    name: str
    rows: list[DatasetRowIn] = []


class DatasetOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    version: int
    row_count: int

    class Config:
        from_attributes = True


class GenerateRowsRequest(BaseModel):
    mode: str = "variation"  # "variation" | "adversarial"
    count: int = 10
    model: str | None = None  # defaults to settings.judge_model (local, free) if omitted

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, mode: str) -> str:
        if mode not in ("variation", "adversarial"):
            raise ValueError("mode must be 'variation' or 'adversarial'")
        return mode

    @field_validator("count")
    @classmethod
    def validate_count(cls, count: int) -> int:
        if not (1 <= count <= 100):
            raise ValueError("count must be between 1 and 100")
        return count
