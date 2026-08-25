from unittest.mock import patch

from evaluators.exact_match import ExactMatchEvaluator, F1Evaluator
from evaluators.faithfulness import FaithfulnessEvaluator
from evaluators.hallucination import HallucinationEvaluator
from evaluators.relevance import AnswerRelevanceEvaluator


def test_exact_match_true():
    assert ExactMatchEvaluator().score(input="q", output="Paris", expected_output=" paris ", context=None, judge_model="x") == 1.0


def test_exact_match_false():
    assert ExactMatchEvaluator().score(input="q", output="London", expected_output="Paris", context=None, judge_model="x") == 0.0


def test_f1_partial_overlap():
    score = F1Evaluator().score(input="q", output="the cat sat", expected_output="the cat sat on mat", context=None, judge_model="x")
    assert 0 < score < 1


def test_f1_no_overlap():
    assert F1Evaluator().score(input="q", output="foo bar", expected_output="baz qux", context=None, judge_model="x") == 0.0


def test_faithfulness_no_context_returns_perfect_score():
    assert FaithfulnessEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x") == 1.0


def test_hallucination_no_context_returns_zero():
    assert HallucinationEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x") == 0.0


@patch("evaluators.faithfulness.ask_judge", return_value=0.8)
def test_faithfulness_with_context_calls_judge(mock_ask):
    score = FaithfulnessEvaluator().score(input="q", output="a", expected_output=None, context="ctx", judge_model="x")
    assert score == 0.8
    mock_ask.assert_called_once()


@patch("evaluators.relevance.ask_judge", return_value=0.5)
def test_answer_relevance_calls_judge(mock_ask):
    score = AnswerRelevanceEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x")
    assert score == 0.5
    mock_ask.assert_called_once()
