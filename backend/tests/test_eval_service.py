import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from evaluators import REGISTRY
from evaluators.base import Evaluator, ScoreResult
from schemas.eval import EvalResultOut
from services.eval_service import render_prompt, run_eval_row, summarize_run


def test_render_prompt_no_template_returns_input():
    assert render_prompt(None, "hello") == "hello"


def test_render_prompt_substitutes_input():
    template = SimpleNamespace(template="Answer this: $input")
    assert render_prompt(template, "what is 2+2?") == "Answer this: what is 2+2?"


def test_run_eval_row_computes_all_requested_metrics():
    row = SimpleNamespace(input="q", expected_output="Paris", context=None)
    scores, details = run_eval_row(judge_model="mock", metrics=["exact_match", "f1"], row=row, output="Paris")
    assert scores == {"exact_match": 1.0, "f1": 1.0}
    # Plain-float evaluators contribute no details.
    assert details == {}


# --- the widened evaluator contract ---


class _OldStyleEvaluator(Evaluator):
    """An evaluator written against the original contract: returns a bare float."""

    name = "old_style"

    def score(self, *, input, output, expected_output, context, judge_model):
        return 0.5


class _NewStyleEvaluator(Evaluator):
    """An evaluator using the widened contract: returns a ScoreResult."""

    name = "new_style"

    def score(self, *, input, output, expected_output, context, judge_model):
        return ScoreResult(0.25, "steps 2 and 3 were redundant", evidence=[2, 3], details={"actual_steps": 5})


def _run(metric):
    row = SimpleNamespace(input="q", expected_output="a", context=None)
    return run_eval_row(judge_model="mock", metrics=[metric], row=row, output="a")


def test_old_style_float_evaluator_still_works(monkeypatch):
    monkeypatch.setitem(REGISTRY, "old_style", _OldStyleEvaluator())
    scores, details = _run("old_style")
    assert scores == {"old_style": 0.5}
    assert details == {}


def test_new_style_rich_evaluator_is_split_into_score_and_details(monkeypatch):
    monkeypatch.setitem(REGISTRY, "new_style", _NewStyleEvaluator())
    scores, details = _run("new_style")
    # The stored score stays a plain float, so every existing numeric reader is unaffected.
    assert scores == {"new_style": 0.25}
    assert type(scores["new_style"]) is float
    assert details == {
        "new_style": {
            "reasoning": "steps 2 and 3 were redundant",
            "evidence": [2, 3],
            "details": {"actual_steps": 5},
        }
    }


def test_score_result_is_a_float_everywhere_a_float_was_expected():
    """Backward compatibility rests on this: a ScoreResult *is* a float, so
    averaging, comparison, and JSON serialisation of existing readers still work."""
    r = ScoreResult(0.4, "why")
    assert r == 0.4 and r < 1.0 and r + 0.1 == pytest.approx(0.5)
    assert sum([r, ScoreResult(0.6)]) / 2 == pytest.approx(0.5)
    assert json.loads(json.dumps({"m": r})) == {"m": 0.4}


def test_old_shaped_stored_row_still_reads(monkeypatch):
    """Rows written before score_details existed have scores as bare numbers and
    score_details NULL. Both the summary path and the API schema must cope."""
    old_row = SimpleNamespace(scores={"f1": 0.8}, score_details=None, error=None, latency_ms=10.0, cost_usd=0.0)
    new_row = SimpleNamespace(
        scores={"f1": 0.6},
        score_details={"f1": {"reasoning": "r", "evidence": [1], "details": {}}},
        error=None,
        latency_ms=20.0,
        cost_usd=0.0,
    )
    db = SimpleNamespace(query=lambda *a, **k: SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(all=lambda: [old_row, new_row])))
    summary = summarize_run(db, SimpleNamespace(id=1, metrics=["f1"]))
    assert summary["avg_scores"]["f1"] == pytest.approx(0.7)

    for row in (old_row, new_row):
        out = EvalResultOut.model_validate(
            SimpleNamespace(id=uuid4(), dataset_row_id=uuid4(), output="o", **{
                "scores": row.scores, "score_details": row.score_details,
                "latency_ms": row.latency_ms, "cost_usd": row.cost_usd})
        )
        assert out.scores == row.scores
        assert out.score_details == row.score_details
