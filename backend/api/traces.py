from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.trace import Trace
from models.user import User
from schemas.trace import TraceCreate, TraceOut, TraceStats
from services.stats import percentile

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=TraceOut, status_code=status.HTTP_201_CREATED)
def create_trace(payload: TraceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trace = Trace(user_id=current_user.id, **payload.model_dump())
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace


@router.get("", response_model=list[TraceOut])
def list_traces(
    limit: int = 50,
    offset: int = 0,
    tag: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Trace).filter(Trace.user_id == current_user.id)
    traces = query.order_by(Trace.created_at.desc()).offset(offset).limit(limit).all()
    if tag:
        traces = [t for t in traces if tag in (t.tags or {}).values() or tag in (t.tags or {})]
    return traces


@router.get("/stats", response_model=TraceStats)
def trace_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    traces = db.query(Trace).filter(Trace.user_id == current_user.id).all()
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
    trace = db.query(Trace).filter(Trace.id == trace_id, Trace.user_id == current_user.id).first()
    if not trace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    return trace
