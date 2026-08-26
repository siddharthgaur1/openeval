from unittest.mock import patch

from evaluators.deepeval_judge import CoherenceEvaluator, ConcisenessEvaluator, ToxicityEvaluator


@patch("evaluators.deepeval_judge.ToxicityMetric")
def test_toxicity_calls_deepeval_metric(mock_metric_cls):
    mock_metric_cls.return_value.measure.return_value = 0.1
    score = ToxicityEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x")
    assert score == 0.1
    mock_metric_cls.return_value.measure.assert_called_once()


@patch("evaluators.deepeval_judge.GEval")
def test_coherence_calls_geval(mock_geval_cls):
    mock_geval_cls.return_value.measure.return_value = 0.85
    score = CoherenceEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x")
    assert score == 0.85


@patch("evaluators.deepeval_judge.GEval")
def test_conciseness_calls_geval(mock_geval_cls):
    mock_geval_cls.return_value.measure.return_value = 0.4
    score = ConcisenessEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x")
    assert score == 0.4
