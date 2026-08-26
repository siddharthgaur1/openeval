from evaluators.semantic_similarity import SemanticSimilarityEvaluator


def test_no_expected_output_returns_zero():
    assert SemanticSimilarityEvaluator().score(input="q", output="a", expected_output=None, context=None, judge_model="x") == 0.0


def test_score_is_a_plain_json_serializable_float():
    # Regression test: model.encode() returns numpy arrays, and an earlier version of
    # this evaluator returned numpy.float32, which crashes json.dumps() when
    # eval_service persists EvalResult.scores to the DB's JSON column.
    score = SemanticSimilarityEvaluator().score(input="q", output="Paris is the capital of France.", expected_output="Paris", context=None, judge_model="x")
    assert type(score) is float
    assert 0.0 <= score <= 1.0
