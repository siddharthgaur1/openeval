from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role, check_quota
from core.database import get_db
from core.metrics import record_llm_cost, traces_ingested_total
from models.dataset import Dataset, DatasetRow
from models.trace import Trace
from models.user import User
from schemas.dataset import DatasetOut
from schemas.trace import FeedbackRequest, TraceCreate, TraceExportRequest, TraceOut, TraceStats
from services.organization_service import get_default_project
from services.stats import percentile

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=TraceOut, status_code=status.HTTP_201_CREATED)
def create_trace(payload: TraceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_id = payload.project_id or get_default_project(db, current_user).id
    project = check_project_role(db, current_user.id, project_id, "member")
    check_quota(db, project, "trace")

    fields = payload.model_dump(exclude={"project_id"})
    trace = Trace(user_id=current_user.id, project_id=project_id, **fields)
    db.add(trace)
    db.commit()
    db.refresh(trace)
    traces_ingested_total.inc()
    record_llm_cost(trace.model, trace.cost_usd)
    return trace


@router.get("", response_model=list[TraceOut])
def list_traces(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
    tag: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_project_role(db, current_user.id, project_id, "viewer")
    query = db.query(Trace).filter(Trace.project_id == project_id)
    traces = query.order_by(Trace.created_at.desc()).offset(offset).limit(limit).all()
    if tag:
        traces = [t for t in traces if tag in (t.tags or {}).values() or tag in (t.tags or {})]
    return traces


@router.get("/stats", response_model=TraceStats)
def trace_stats(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    traces = db.query(Trace).filter(Trace.project_id == project_id).all()
    latencies = [t.latency_ms for t in traces]
    return TraceStats(
        count=len(traces),
        total_cost_usd=sum(t.cost_usd for t in traces),
        p50_latency_ms=percentile(latencies, 0.50),
        p95_latency_ms=percentile(latencies, 0.95),
        p99_latency_ms=percentile(latencies, 0.99),
    )


@router.get("/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    if not trace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    check_project_role(db, current_user.id, trace.project_id, "viewer")
    return trace


@router.post("/{trace_id}/feedback", response_model=TraceOut)
def submit_feedback(trace_id: UUID, payload: FeedbackRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    if not trace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    check_project_role(db, current_user.id, trace.project_id, "member")
    # Reassign (not mutate) the JSON column so SQLAlchemy detects the change.
    trace.tags = {**(trace.tags or {}), "feedback": {"score": payload.score, "comment": payload.comment}}
    db.commit()
    db.refresh(trace)
    return trace


@router.post("/export", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def export_traces_as_dataset(payload: TraceExportRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Bulk-export selected traces (prompt -> input, response -> expected_output)
    as a new one-off dataset, e.g. for turning production traffic into eval fixtures.
    """
    traces = db.query(Trace).filter(Trace.id.in_(payload.trace_ids)).all()
    if not traces:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching traces found")
    project_ids = {t.project_id for t in traces}
    if len(project_ids) > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All exported traces must belong to the same project")
    project_id = project_ids.pop()
    check_project_role(db, current_user.id, project_id, "member")

    dataset = Dataset(
        user_id=current_user.id,
        project_id=project_id,
        name=payload.dataset_name,
        rows=[DatasetRow(input=t.prompt, expected_output=t.response, tags={"source_trace_id": str(t.id)}) for t in traces],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return DatasetOut(id=dataset.id, project_id=dataset.project_id, name=dataset.name, version=dataset.version, row_count=len(dataset.rows))
