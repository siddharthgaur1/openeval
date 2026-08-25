from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.eval import EvalRun
from models.experiment import Experiment
from models.user import User
from schemas.experiment import ExperimentCreate, ExperimentOut, SetBaselineRequest
from services.eval_service import compare_runs
from services.webhook_service import dispatch_regression_webhooks

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _validate_run_ids(db: Session, user_id, run_ids: list[UUID]):
    if not run_ids:
        return
    count = db.query(EvalRun).filter(EvalRun.id.in_(run_ids), EvalRun.user_id == user_id).count()
    if count != len(set(run_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more eval runs not found")


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _validate_run_ids(db, current_user.id, payload.run_ids + ([payload.baseline_run_id] if payload.baseline_run_id else []))
    experiment = Experiment(
        user_id=current_user.id,
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
def list_experiments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Experiment).filter(Experiment.user_id == current_user.id).order_by(Experiment.created_at.desc()).all()


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id, Experiment.user_id == current_user.id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return experiment


@router.post("/{experiment_id}/baseline", response_model=ExperimentOut)
def set_baseline(experiment_id: UUID, payload: SetBaselineRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id, Experiment.user_id == current_user.id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    _validate_run_ids(db, current_user.id, [payload.run_id])
    experiment.baseline_run_id = payload.run_id
    if str(payload.run_id) not in experiment.run_ids:
        experiment.run_ids = [*experiment.run_ids, str(payload.run_id)]
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("/{experiment_id}/compare")
def compare_experiment(experiment_id: UUID, regression_threshold: float = 0.05, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id, Experiment.user_id == current_user.id).first()
    if not experiment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    if not experiment.run_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Experiment has no eval runs to compare")

    run_ids = experiment.run_ids
    if experiment.baseline_run_id and str(experiment.baseline_run_id) in run_ids:
        run_ids = [str(experiment.baseline_run_id)] + [r for r in run_ids if r != str(experiment.baseline_run_id)]

    comparison = compare_runs(db, run_ids, regression_threshold)
    dispatch_regression_webhooks(db, current_user.id, comparison)
    return comparison
