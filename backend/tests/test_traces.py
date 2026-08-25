from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.traces import export_traces_as_dataset, submit_feedback
from models.project import Project
from models.organization import Membership
from models.trace import Trace
from schemas.trace import FeedbackRequest, TraceExportRequest


def test_submit_feedback_merges_into_tags_without_mutating_in_place():
    trace = MagicMock(project_id=uuid4(), tags={"env": "prod"})
    project = MagicMock(organization_id=uuid4())
    membership = MagicMock(role="member")
    db = MagicMock()
    # Order of internal db.query(...).filter(...).first() calls: trace lookup,
    # then check_project_role's project lookup, then its membership lookup.
    db.query.return_value.filter.return_value.first.side_effect = [trace, project, membership]

    result = submit_feedback(
        trace_id=uuid4(),
        payload=FeedbackRequest(score=1, comment="looks right"),
        db=db,
        current_user=MagicMock(),
    )

    assert result.tags == {"env": "prod", "feedback": {"score": 1, "comment": "looks right"}}
    db.commit.assert_called_once()


def test_submit_feedback_404_when_trace_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        submit_feedback(trace_id=uuid4(), payload=FeedbackRequest(score=-1), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 404


def test_export_traces_as_dataset_builds_rows_from_prompt_response():
    project_id = uuid4()
    traces = [
        MagicMock(id=uuid4(), project_id=project_id, prompt="p1", response="r1"),
        MagicMock(id=uuid4(), project_id=project_id, prompt="p2", response="r2"),
    ]
    project = MagicMock(organization_id=uuid4())
    membership = MagicMock(role="member")

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is Trace:
            q.filter.return_value.all.return_value = traces
        elif model is Project:
            q.filter.return_value.first.return_value = project
        elif model is Membership:
            q.filter.return_value.first.return_value = membership
        return q

    db.query.side_effect = query_side_effect
    # A real DB would populate id/version (default=uuid4, default=1) on flush;
    # the mock db.refresh() is a no-op, so seed them here to mirror that.
    def fake_refresh(dataset):
        dataset.id = uuid4()
        dataset.version = 1

    db.refresh.side_effect = fake_refresh

    result = export_traces_as_dataset(
        payload=TraceExportRequest(trace_ids=[t.id for t in traces], dataset_name="my-export"),
        db=db,
        current_user=MagicMock(),
    )

    assert result.name == "my-export"
    assert result.row_count == 2
    db.add.assert_called_once()
    added_dataset = db.add.call_args[0][0]
    assert [r.input for r in added_dataset.rows] == ["p1", "p2"]
    assert [r.expected_output for r in added_dataset.rows] == ["r1", "r2"]


def test_export_traces_as_dataset_404_when_no_traces_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    with pytest.raises(HTTPException) as exc_info:
        export_traces_as_dataset(payload=TraceExportRequest(trace_ids=[uuid4()]), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 404


def test_export_traces_as_dataset_rejects_mixed_projects():
    traces = [MagicMock(id=uuid4(), project_id=uuid4()), MagicMock(id=uuid4(), project_id=uuid4())]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = traces

    with pytest.raises(HTTPException) as exc_info:
        export_traces_as_dataset(payload=TraceExportRequest(trace_ids=[t.id for t in traces]), db=db, current_user=MagicMock())
    assert exc_info.value.status_code == 400
