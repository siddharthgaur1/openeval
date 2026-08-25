from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.database import get_db
from core.metrics import record_llm_cost, traces_ingested_total
from models.trace import Trace
from models.user import User
from schemas.trace import TraceCreate, TraceOut, TraceStats
from services.organization_service import get_default_project
from services.stats import percentile

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=TraceOut, status_code=status.HTTP_201_CREATED)
def create_trace(payload: TraceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_id = payload.project_id or get_default_project(db, current_user).id
    check_project_role(db, current_user.id, project_id, "member")

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
