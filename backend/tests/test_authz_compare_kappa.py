"""Regression tests: /evals/compare and /experiments/{id}/compare let a viewer fire
regression webhooks."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import api.rbac as rbac
from api import evals as evals_api
from api import experiments as experiments_api
from models.eval import EvalRun
from models.experiment import Experiment
from models.project import Project
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

