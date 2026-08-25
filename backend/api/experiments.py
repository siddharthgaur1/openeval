from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.database import get_db
from models.eval import EvalRun
from models.experiment import Experiment
from models.user import User
from schemas.experiment import ExperimentCreate, ExperimentOut, SetBaselineRequest
from services.eval_service import compare_runs
from services.organization_service import get_default_project
from services.webhook_service import dispatch_regression_webhooks

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _validate_run_ids_in_project(db: Session, project_id, run_ids: list[UUID]) -> None:
    if not run_ids:
        return
    count = db.query(EvalRun).filter(EvalRun.id.in_(run_ids), EvalRun.project_id == project_id).count()
    if count != len(set(run_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more eval runs not found in this project")


def _resolve_experiment_project_id(db: Session, current_user: User, payload: ExperimentCreate) -> UUID:
    if payload.project_id:
        return payload.project_id
    if payload.run_ids:
        first_run = db.query(EvalRun).filter(EvalRun.id == payload.run_ids[0]).first()
        if first_run:
            return first_run.project_id
    return get_default_project(db, current_user).id


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_id = _resolve_experiment_project_id(db, current_user, payload)
    check_project_role(db, current_user.id, project_id, "member")
    _validate_run_ids_in_project(db, project_id, payload.run_ids + ([payload.baseline_run_id] if payload.baseline_run_id else []))

    experiment = Experiment(
        user_id=current_user.id,
        project_id=project_id,
        name=payload.name,
        baseline_run_id=payload.baseline_run_id,
        run_ids=[str(rid) for rid in payload.run_ids],
        notes=payload.notes,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("", response_model=list[ExperimentOut])
def list_experiments(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    return db.query(Experiment).filter(Experiment.project_id == project_id).order_by(Experiment.created_at.desc()).all()


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    check_project_role(db, current_user.id, experiment.project_id, "viewer")
    return experiment


@router.post("/{experiment_id}/baseline", response_model=ExperimentOut)
def set_baseline(experiment_id: UUID, payload: SetBaselineRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    check_project_role(db, current_user.id, experiment.project_id, "member")
    _validate_run_ids_in_project(db, experiment.project_id, [payload.run_id])

    experiment.baseline_run_id = payload.run_id
    if str(payload.run_id) not in experiment.run_ids:
        experiment.run_ids = [*experiment.run_ids, str(payload.run_id)]
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("/{experiment_id}/compare")
def compare_experiment(experiment_id: UUID, regression_threshold: float = 0.05, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    check_project_role(db, current_user.id, experiment.project_id, "viewer")
    if not experiment.run_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Experiment has no eval runs to compare")

    run_ids = experiment.run_ids
    if experiment.baseline_run_id and str(experiment.baseline_run_id) in run_ids:
        run_ids = [str(experiment.baseline_run_id)] + [r for r in run_ids if r != str(experiment.baseline_run_id)]

    comparison = compare_runs(db, run_ids, regression_threshold)
    run_project_map = {run_id: experiment.project_id for run_id in run_ids}
    dispatch_regression_webhooks(db, comparison, run_project_map)
    return comparison
