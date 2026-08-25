from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.annotation import Annotation, AnnotationQueueItem
from models.dataset import Dataset, DatasetRow
from models.trace import Trace
from models.user import User
from schemas.annotation import (
    AnnotationOut,
    AnnotationQueueItemOut,
    AssignAnnotationRequest,
    KappaRequest,
    KappaResult,
    SubmitAnnotationRequest,
)
from schemas.dataset import DatasetOut
from services.annotation_service import cohen_kappa, export_annotations_as_dataset_rows

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.post("/assign", response_model=AnnotationQueueItemOut, status_code=status.HTTP_201_CREATED)
def assign_annotation(payload: AssignAnnotationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trace = db.query(Trace).filter(Trace.id == payload.trace_id, Trace.user_id == current_user.id).first()
    if not trace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")

    item = AnnotationQueueItem(
        trace_id=payload.trace_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        created_by_user_id=current_user.id,
        rubric=payload.rubric,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/queue", response_model=list[AnnotationQueueItemOut])
def my_queue(status_filter: str = "pending", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(AnnotationQueueItem).filter(AnnotationQueueItem.assigned_to_user_id == current_user.id)
    if status_filter:
        query = query.filter(AnnotationQueueItem.status == status_filter)
    return query.order_by(AnnotationQueueItem.created_at).all()


@router.post("/queue/{item_id}/submit", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED)
def submit_annotation(item_id: UUID, payload: SubmitAnnotationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(AnnotationQueueItem).filter(AnnotationQueueItem.id == item_id, AnnotationQueueItem.assigned_to_user_id == current_user.id).first()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue item not found")
    if item.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already annotated")

    annotation = Annotation(
        queue_item_id=item.id,
        trace_id=item.trace_id,
        annotator_id=current_user.id,
        scores=payload.scores,
        comment=payload.comment,
    )
    item.status = "completed"
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


@router.post("/kappa", response_model=KappaResult)
def inter_annotator_agreement(payload: KappaRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    a_annotations = {a.trace_id: a.scores.get(payload.criterion) for a in db.query(Annotation).filter(Annotation.annotator_id == payload.annotator_a_id).all()}
    b_annotations = {a.trace_id: a.scores.get(payload.criterion) for a in db.query(Annotation).filter(Annotation.annotator_id == payload.annotator_b_id).all()}

    shared_trace_ids = [tid for tid in a_annotations if tid in b_annotations and a_annotations[tid] is not None and b_annotations[tid] is not None]
    labels_a = [a_annotations[tid] for tid in shared_trace_ids]
    labels_b = [b_annotations[tid] for tid in shared_trace_ids]

    return KappaResult(criterion=payload.criterion, n_shared_items=len(shared_trace_ids), kappa=cohen_kappa(labels_a, labels_b))


@router.post("/export", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def export_annotations_dataset(name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    annotations = (
        db.query(Annotation)
        .join(AnnotationQueueItem, Annotation.queue_item_id == AnnotationQueueItem.id)
        .filter(AnnotationQueueItem.created_by_user_id == current_user.id)
        .all()
    )
    if not annotations:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No annotations to export")

    trace_ids = {a.trace_id for a in annotations}
    traces_by_id = {t.id: t for t in db.query(Trace).filter(Trace.id.in_(trace_ids)).all()}

    row_dicts = export_annotations_as_dataset_rows(annotations, traces_by_id)
    dataset = Dataset(user_id=current_user.id, name=name, rows=[DatasetRow(**row) for row in row_dicts])
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return DatasetOut(id=dataset.id, name=dataset.name, version=dataset.version, row_count=len(dataset.rows))
