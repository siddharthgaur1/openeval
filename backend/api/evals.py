import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.config import settings
from core.database import get_db
from core.redis import progress_channel, redis_client
from models.dataset import Dataset
from models.eval import EvalRun
from models.user import User
from schemas.eval import CompareRequest, EvalRunCreate, EvalRunDetail, EvalRunOut
from services.eval_service import compare_runs
from services.webhook_service import dispatch_regression_webhooks
from workers.tasks import run_eval_job

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
def create_eval_run(payload: EvalRunCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
    if not dataset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    # The eval run always lives in its dataset's project - keeps a run's access
    # control unambiguous even if the caller belongs to several projects.
    check_project_role(db, current_user.id, dataset.project_id, "member")

    eval_run = EvalRun(
        user_id=current_user.id,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        prompt_template_id=payload.prompt_template_id,
        name=payload.name,
        target_model=payload.target_model,
        judge_model=payload.judge_model or settings.judge_model,
        metrics=payload.metrics,
        status="pending",
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)

    run_eval_job.delay(str(eval_run.id))
    return eval_run


@router.get("", response_model=list[EvalRunOut])
def list_eval_runs(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    return (
        db.query(EvalRun)
        .filter(EvalRun.project_id == project_id)
        .order_by(EvalRun.created_at.desc())
        .all()
    )


@router.get("/{eval_run_id}", response_model=EvalRunDetail)
def get_eval_run(eval_run_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    eval_run = db.query(EvalRun).filter(EvalRun.id == eval_run_id).first()
    if not eval_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eval run not found")
    check_project_role(db, current_user.id, eval_run.project_id, "viewer")
    return eval_run


@router.get("/{eval_run_id}/status")
async def stream_eval_status(eval_run_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """SSE stream of eval run progress. Emits one event per row completed/failed,
    plus a final event when the run finishes. Closes automatically once the run
    reaches a terminal status.
    """
    eval_run = db.query(EvalRun).filter(EvalRun.id == eval_run_id).first()
    if not eval_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eval run not found")
    check_project_role(db, current_user.id, eval_run.project_id, "viewer")

    async def event_stream():
        yield f"data: {json.dumps({'status': eval_run.status, 'total_rows': eval_run.total_rows, 'completed_rows': eval_run.completed_rows, 'failed_rows': eval_run.failed_rows})}\n\n"
        if eval_run.status in ("completed", "failed"):
            return

        # ponytail: sync redis-py pubsub polled from an async generator - fine for MVP
        # concurrency, switch to redis.asyncio if this endpoint needs many concurrent streams.
        pubsub = redis_client.pubsub()
        pubsub.subscribe(progress_channel(str(eval_run_id)))
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    payload = json.loads(message["data"])
                    yield f"data: {json.dumps(payload)}\n\n"
                    if payload.get("status") in ("completed", "failed"):
                        break
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.1)
        finally:
            pubsub.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/compare")
def compare_eval_runs(payload: CompareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = db.query(EvalRun).filter(EvalRun.id.in_(payload.run_ids)).all()
    if len(runs) != len(payload.run_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more eval runs not found")
    for run in runs:
        check_project_role(db, current_user.id, run.project_id, "viewer")

    comparison = compare_runs(db, payload.run_ids, payload.regression_threshold)
    run_project_map = {str(run.id): run.project_id for run in runs}
    dispatch_regression_webhooks(db, comparison, run_project_map)
    return comparison
