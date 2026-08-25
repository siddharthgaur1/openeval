import csv
import io
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.config import settings
from core.database import get_db
from models.dataset import Dataset, DatasetRow
from models.user import User
from schemas.dataset import DatasetCreate, DatasetOut, DatasetRowOut, GenerateRowsRequest
from services.synthetic_service import generate_rows

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _to_out(dataset: Dataset) -> DatasetOut:
    return DatasetOut(id=dataset.id, name=dataset.name, version=dataset.version, row_count=len(dataset.rows))


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = Dataset(user_id=current_user.id, name=payload.name)
    dataset.rows = [DatasetRow(**row.model_dump()) for row in payload.rows]
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _to_out(dataset)


@router.post("/upload", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def upload_dataset(name: str, file: UploadFile, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw = (await file.read()).decode("utf-8")
    rows: list[DatasetRow] = []

    if file.filename and file.filename.endswith(".jsonl"):
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rows.append(_row_from_record(record))
    elif file.filename and file.filename.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(raw))
        for record in reader:
            rows.append(_row_from_record(record))
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv and .jsonl files are supported")

    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No rows parsed from file")

    dataset = Dataset(user_id=current_user.id, name=name, rows=rows)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _to_out(dataset)


def _row_from_record(record: dict) -> DatasetRow:
    if "input" not in record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Each row must have an 'input' column")
    tags = record.get("tags") or {}
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = {}
    return DatasetRow(
        input=record["input"],
        expected_output=record.get("expected_output") or record.get("output"),
        context=record.get("context"),
        tags=tags,
    )


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    datasets = db.query(Dataset).filter(Dataset.user_id == current_user.id).all()
    return [_to_out(d) for d in datasets]


@router.get("/{dataset_id}/rows", response_model=list[DatasetRowOut])
def get_dataset_rows(dataset_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id).first()
    if not dataset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    return dataset.rows


@router.post("/{dataset_id}/version", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_new_version(dataset_id: UUID, payload: DatasetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id).first()
    if not base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    new_version = Dataset(user_id=current_user.id, name=base.name, version=base.version + 1)
    new_version.rows = [DatasetRow(**row.model_dump()) for row in payload.rows]
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return _to_out(new_version)


@router.post("/{dataset_id}/generate", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def generate_dataset_rows(dataset_id: UUID, payload: GenerateRowsRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate new rows from the dataset's existing rows as seeds (via an LLM), and
    append them as a new dataset version. `mode` is 'variation' (realistic paraphrases
    of the seeds) or 'adversarial' (edge cases / prompt injection / ambiguous input).
    """
    base = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id).first()
    if not base:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if not base.rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dataset has no rows to use as seeds")

    generated = generate_rows(model=payload.model or settings.judge_model, mode=payload.mode, seed_rows=base.rows, count=payload.count)
    if not generated:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Model did not return parseable rows - try again or a different model")

    new_version = Dataset(user_id=current_user.id, name=base.name, version=base.version + 1)
    new_version.rows = [DatasetRow(input=r["input"], expected_output=r["expected_output"], context=r["context"], tags=r["tags"]) for r in generated]
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return _to_out(new_version)
