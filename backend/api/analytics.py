from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.database import get_db
from models.trace import Trace
from models.user import User
from services.analytics_service import cost_by_day, cost_by_model, latency_by_model, project_monthly_cost, usage_by_tag

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/cost")
def cost_analytics(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    traces = db.query(Trace).filter(Trace.project_id == project_id).all()
    return {
        "by_model": cost_by_model(traces),
        "by_day": cost_by_day(traces),
        "total_usd": sum(t.cost_usd for t in traces),
        "projected_monthly_usd": project_monthly_cost(traces),
    }


@router.get("/latency")
def latency_analytics(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    traces = db.query(Trace).filter(Trace.project_id == project_id).all()
    return {"by_model": latency_by_model(traces)}


@router.get("/usage")
def usage_analytics(project_id: UUID, tag: str = "environment", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    traces = db.query(Trace).filter(Trace.project_id == project_id).all()
    return {
        "trace_count": len(traces),
        "by_model": {model: sum(1 for t in traces if t.model == model) for model in {t.model for t in traces}},
        f"by_tag_{tag}": usage_by_tag(traces, tag),
    }
