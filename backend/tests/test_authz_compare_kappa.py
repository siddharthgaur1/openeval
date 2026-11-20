"""Regression tests for two authorization gaps:
- /evals/compare and /experiments/{id}/compare let a viewer fire regression webhooks.
- /annotations/kappa checked only the first shared trace's project, so a caller who
  could see one project got kappa computed over annotations from projects they can't see.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.rbac as rbac
from api import evals as evals_api
from api import experiments as experiments_api
from api.annotations import inter_annotator_agreement
from core.database import Base
from models.annotation import Annotation, AnnotationQueueItem
from models.eval import EvalRun
from models.experiment import Experiment
from models.organization import Membership, Organization
from models.project import Project
from models.trace import Trace
from models.user import User
from schemas.annotation import KappaRequest
from schemas.eval import CompareRequest

REGRESSED = {"baseline_run_id": None, "runs": [{"eval_run_id": "x", "regressions": ["f1"]}]}


def _query_by_model(rows: dict):
    """db.query(Model) -> a chain whose .filter(...).first()/.all() return rows[Model]."""

    def query(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = rows.get(model)
        q.filter.return_value.all.return_value = rows.get(model)
        return q

    return query


def _as_viewer(monkeypatch, sent):
    monkeypatch.setattr(rbac, "get_membership", lambda *a, **k: SimpleNamespace(role="viewer"))
    monkeypatch.setattr(evals_api, "dispatch_regression_webhooks", lambda db, comparison, run_map: sent.append(run_map))
    monkeypatch.setattr(experiments_api, "dispatch_regression_webhooks", lambda db, comparison, run_map: sent.append(run_map))
    monkeypatch.setattr(evals_api, "compare_runs", lambda *a, **k: REGRESSED)
    monkeypatch.setattr(experiments_api, "compare_runs", lambda *a, **k: REGRESSED)


def test_viewer_compare_evals_returns_comparison_but_fires_no_webhook(monkeypatch):
    sent = []
    _as_viewer(monkeypatch, sent)
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    run = SimpleNamespace(id=uuid4(), project_id=project.id)
    db = MagicMock()
    db.query.side_effect = _query_by_model({EvalRun: [run], Project: project})

    result = evals_api.compare_eval_runs(CompareRequest(run_ids=[run.id]), db=db, current_user=SimpleNamespace(id=uuid4()))

    assert result == REGRESSED
    assert all(not run_map for run_map in sent)


def test_viewer_compare_experiment_returns_comparison_but_fires_no_webhook(monkeypatch):
    sent = []
    _as_viewer(monkeypatch, sent)
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    experiment = SimpleNamespace(id=uuid4(), project_id=project.id, run_ids=[str(uuid4())], baseline_run_id=None)
    db = MagicMock()
    db.query.side_effect = _query_by_model({Experiment: experiment, Project: project})

    result = experiments_api.compare_experiment(experiment.id, db=db, current_user=SimpleNamespace(id=uuid4()))

    assert result == REGRESSED
    assert all(not run_map for run_map in sent)


def test_member_compare_evals_still_fires_webhook(monkeypatch):
    sent = []
    _as_viewer(monkeypatch, sent)
    monkeypatch.setattr(rbac, "get_membership", lambda *a, **k: SimpleNamespace(role="member"))
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    run = SimpleNamespace(id=uuid4(), project_id=project.id)
    db = MagicMock()
    db.query.side_effect = _query_by_model({EvalRun: [run], Project: project})

    evals_api.compare_eval_runs(CompareRequest(run_ids=[run.id]), db=db, current_user=SimpleNamespace(id=uuid4()))

    assert sent == [{str(run.id): project.id}]


def test_kappa_ignores_annotations_on_traces_the_caller_cannot_see():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    caller, ann_a, ann_b = (User(email=f"{n}@x.test", hashed_password="x") for n in ("caller", "a", "b"))
    db.add_all([caller, ann_a, ann_b])
    shared_org, private_org = Organization(name="shared"), Organization(name="private")
    db.add_all([shared_org, private_org])
    db.flush()
    visible_project = Project(organization_id=shared_org.id, name="visible")
    hidden_project = Project(organization_id=private_org.id, name="hidden")
    db.add_all([visible_project, hidden_project, Membership(organization_id=shared_org.id, user_id=caller.id, role="viewer")])
    db.flush()

    # The visible trace comes first, so the old "check one sample trace" logic passed
    # its check and then counted the two hidden traces too.
    for project, a_score, b_score in [(visible_project, 1, 1), (hidden_project, 1, 0), (hidden_project, 0, 1)]:
        trace = Trace(user_id=caller.id, project_id=project.id, model="m", prompt="p")
        db.add(trace)
        db.flush()
        for annotator, score in ((ann_a, a_score), (ann_b, b_score)):
            item = AnnotationQueueItem(trace_id=trace.id, assigned_to_user_id=annotator.id, created_by_user_id=caller.id)
            db.add(item)
            db.flush()
            db.add(Annotation(queue_item_id=item.id, trace_id=trace.id, annotator_id=annotator.id, scores={"ok": score}))
    db.commit()

    result = inter_annotator_agreement(KappaRequest(criterion="ok", annotator_a_id=ann_a.id, annotator_b_id=ann_b.id), db=db, current_user=caller)

    assert result.n_shared_items == 1
