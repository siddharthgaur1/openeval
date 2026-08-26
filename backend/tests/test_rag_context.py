from unittest.mock import patch

from evaluators.rag_context import (
    ContextEntityRecallEvaluator,
    ContextPrecisionEvaluator,
    ContextRecallEvaluator,
    NoiseRobustnessEvaluator,
)


def test_context_precision_no_context_returns_zero():
    assert ContextPrecisionEvaluator().score(input="q", output="a", expected_output="e", context=None, judge_model="x") == 0.0


def test_context_precision_no_expected_output_returns_zero():
    assert ContextPrecisionEvaluator().score(input="q", output="a", expected_output=None, context="ctx", judge_model="x") == 0.0


@patch("evaluators.rag_context.ContextualPrecisionMetric")
def test_context_precision_calls_deepeval_metric(mock_metric_cls):
    mock_metric_cls.return_value.measure.return_value = 0.6
    score = ContextPrecisionEvaluator().score(input="q", output="a", expected_output="e", context="chunk one\n---\nchunk two", judge_model="x")
    assert score == 0.6
    test_case = mock_metric_cls.return_value.measure.call_args[0][0]
    assert test_case.retrieval_context == ["chunk one", "chunk two"]


@patch("evaluators.rag_context.ContextualRecallMetric")
def test_context_recall_calls_deepeval_metric(mock_metric_cls):
    mock_metric_cls.return_value.measure.return_value = 0.7
    score = ContextRecallEvaluator().score(input="q", output="a", expected_output="e", context="ctx", judge_model="x")
    assert score == 0.7


def test_context_entity_recall_requires_context_and_expected():
    assert ContextEntityRecallEvaluator().score(input="q", output="a", expected_output=None, context="ctx", judge_model="x") == 0.0
    assert ContextEntityRecallEvaluator().score(input="q", output="a", expected_output="e", context=None, judge_model="x") == 0.0


@patch("evaluators.rag_context.GEval")
def test_context_entity_recall_calls_geval(mock_geval_cls):
    mock_geval_cls.return_value.measure.return_value = 0.9
    score = ContextEntityRecallEvaluator().score(input="q", output="a", expected_output="e", context="ctx", judge_model="x")
    assert score == 0.9


def test_noise_robustness_no_context_returns_perfect_score():
    assert NoiseRobustnessEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x") == 1.0


@patch("evaluators.rag_context.GEval")
def test_noise_robustness_calls_geval(mock_geval_cls):
    mock_geval_cls.return_value.measure.return_value = 0.3
    score = NoiseRobustnessEvaluator().score(input="q", output="a", expected_output=None, context="ctx", judge_model="x")
    assert score == 0.3
