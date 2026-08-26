from types import SimpleNamespace

from services.eval_service import render_prompt, run_eval_row


def test_render_prompt_no_template_returns_input():
    assert render_prompt(None, "hello") == "hello"


def test_render_prompt_substitutes_input():
    template = SimpleNamespace(template="Answer this: $input")
    assert render_prompt(template, "what is 2+2?") == "Answer this: what is 2+2?"


def test_run_eval_row_computes_all_requested_metrics():
    row = SimpleNamespace(input="q", expected_output="Paris", context=None)
    scores = run_eval_row(judge_model="mock", metrics=["exact_match", "f1"], row=row, output="Paris")
    assert scores == {"exact_match": 1.0, "f1": 1.0}
