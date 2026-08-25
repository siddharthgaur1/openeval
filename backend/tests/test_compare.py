import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.eval_service import compare_runs


def _make_run(run_id, summary):
    return SimpleNamespace(id=run_id, name=f"run-{run_id}", summary=summary)


def _make_result(row_id, run_id, scores, output="out"):
    return SimpleNamespace(dataset_row_id=row_id, eval_run_id=run_id, scores=scores, output=output)


def test_compare_runs_flags_regression_below_threshold():
    baseline_id, candidate_id = uuid.uuid4(), uuid.uuid4()
    row_id = uuid.uuid4()

    baseline = _make_run(baseline_id, {"avg_scores": {"exact_match": 0.9}})
    candidate = _make_run(candidate_id, {"avg_scores": {"exact_match": 0.5}})

    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [
        [baseline, candidate],  # EvalRun lookup
        [_make_result(row_id, baseline_id, {"exact_match": 0.9})],  # baseline results
        [_make_result(row_id, candidate_id, {"exact_match": 0.5})],  # candidate results (t-test)
        [_make_result(row_id, candidate_id, {"exact_match": 0.5})],  # candidate results (row diff)
    ]

    result = compare_runs(db, [baseline_id, candidate_id], regression_threshold=0.05)

    assert result["baseline_run_id"] == str(baseline_id)
    candidate_out = next(r for r in result["runs"] if r["eval_run_id"] == str(candidate_id))
    assert "exact_match" in candidate_out["regressions"]
    assert candidate_out["delta_vs_baseline"]["exact_match"] == -0.4
    assert len(candidate_out["row_diffs"]) == 1


def test_compare_runs_empty_when_no_matching_runs():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    result = compare_runs(db, [uuid.uuid4()], regression_threshold=0.05)
    assert result == {"baseline_run_id": None, "runs": []}
