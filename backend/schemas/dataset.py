from uuid import UUID

from pydantic import BaseModel


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
    name: str
    rows: list[DatasetRowIn] = []


class DatasetOut(BaseModel):
    id: UUID
    name: str
    version: int
    row_count: int

    class Config:
        from_attributes = True
