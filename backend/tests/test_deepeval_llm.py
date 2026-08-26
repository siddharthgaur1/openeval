import asyncio
from unittest.mock import MagicMock, patch

from evaluators.deepeval_llm import LiteLLMDeepEvalModel


def _mock_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


@patch("evaluators.deepeval_llm.litellm.completion")
def test_generate_returns_completion_text(mock_completion):
    mock_completion.return_value = _mock_response("hello")
    model = LiteLLMDeepEvalModel("ollama/llama3")
    assert model.generate("prompt") == "hello"
    assert model.get_model_name() == "ollama/llama3"


@patch("evaluators.deepeval_llm.litellm.acompletion")
def test_a_generate_returns_completion_text(mock_acompletion):
    async def _fake(*args, **kwargs):
        return _mock_response("async hello")

    mock_acompletion.side_effect = _fake
    model = LiteLLMDeepEvalModel("ollama/llama3")
    assert asyncio.run(model.a_generate("prompt")) == "async hello"
