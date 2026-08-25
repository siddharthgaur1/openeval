from unittest.mock import patch

from evaluators.deterministic_extra import BleuEvaluator, JsonValidityEvaluator, RegexMatchEvaluator, RougeLEvaluator
from evaluators.semantic_similarity import SemanticSimilarityEvaluator


def test_json_validity_true():
    assert JsonValidityEvaluator().score(input="q", output='{"a": 1}', expected_output=None, context=None, judge_model="x") == 1.0


def test_json_validity_false():
    assert JsonValidityEvaluator().score(input="q", output="not json", expected_output=None, context=None, judge_model="x") == 0.0


def test_regex_match_true():
    score = RegexMatchEvaluator().score(input="q", output="order #12345 confirmed", expected_output=r"#\d+", context=None, judge_model="x")
    assert score == 1.0


def test_regex_match_false():
    score = RegexMatchEvaluator().score(input="q", output="no numbers here", expected_output=r"#\d+", context=None, judge_model="x")
    assert score == 0.0


def test_regex_match_invalid_pattern_returns_zero():
    score = RegexMatchEvaluator().score(input="q", output="text", expected_output="(unclosed", context=None, judge_model="x")
    assert score == 0.0


def test_bleu_identical_is_one():
    score = BleuEvaluator().score(input="q", output="the cat sat on the mat", expected_output="the cat sat on the mat", context=None, judge_model="x")
    assert score == 1.0


def test_bleu_no_overlap_is_zero():
    score = BleuEvaluator().score(input="q", output="completely different words here", expected_output="the cat sat on mat", context=None, judge_model="x")
    assert score == 0.0


def test_rouge_l_identical_is_one():
    score = RougeLEvaluator().score(input="q", output="the cat sat on the mat", expected_output="the cat sat on the mat", context=None, judge_model="x")
    assert score == 1.0


def test_rouge_l_partial_overlap():
    score = RougeLEvaluator().score(input="q", output="the cat sat", expected_output="the cat sat on the mat", context=None, judge_model="x")
    assert 0 < score < 1


@patch("evaluators.semantic_similarity._get_model")
def test_semantic_similarity_identical_vectors(mock_get_model):
    mock_model = mock_get_model.return_value
    mock_model.encode.return_value = [[1.0, 0.0], [1.0, 0.0]]
    score = SemanticSimilarityEvaluator().score(input="q", output="a", expected_output="b", context=None, judge_model="x")
    assert score == 1.0


def test_semantic_similarity_no_expected_returns_zero():
    assert SemanticSimilarityEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x") == 0.0
