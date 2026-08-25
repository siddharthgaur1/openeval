from unittest.mock import MagicMock, patch

from evaluators.llm_judge import ask_judge


def _mock_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


@patch("evaluators.llm_judge.completion")
def test_ask_judge_parses_json_score(mock_completion):
    mock_completion.return_value = _mock_response('{"score": 0.7, "reason": "ok"}')
    assert ask_judge("mock-model", "prompt") == 0.7


@patch("evaluators.llm_judge.completion")
def test_ask_judge_clamps_out_of_range_score(mock_completion):
    mock_completion.return_value = _mock_response('{"score": 1.5}')
    assert ask_judge("mock-model", "prompt") == 1.0


@patch("evaluators.llm_judge.completion")
def test_ask_judge_falls_back_to_bare_number(mock_completion):
    mock_completion.return_value = _mock_response("I'd say 0.4 roughly")
    assert ask_judge("mock-model", "prompt") == 0.4


@patch("evaluators.llm_judge.completion")
def test_ask_judge_returns_zero_when_unparseable(mock_completion):
    mock_completion.return_value = _mock_response("no idea")
    assert ask_judge("mock-model", "prompt") == 0.0
