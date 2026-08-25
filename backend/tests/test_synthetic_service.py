from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.synthetic_service import _parse_rows, build_generation_prompt, generate_rows


def test_parse_rows_extracts_valid_json_array():
    text = 'Here you go:\n[{"input": "q1", "expected_output": "a1", "context": ""}, {"input": "q2", "expected_output": "a2"}]'
    rows = _parse_rows(text)
    assert len(rows) == 2
    assert rows[0]["input"] == "q1"
    assert rows[0]["tags"] == {"synthetic": True}


def test_parse_rows_returns_empty_on_no_json():
    assert _parse_rows("sorry, I can't do that") == []


def test_parse_rows_skips_entries_without_input():
    text = '[{"expected_output": "a1"}, {"input": "q2", "expected_output": "a2"}]'
    rows = _parse_rows(text)
    assert len(rows) == 1
    assert rows[0]["input"] == "q2"


def test_build_generation_prompt_variation_includes_seeds_and_count():
    seeds = [SimpleNamespace(input="What is 2+2?", expected_output="4")]
    prompt = build_generation_prompt("variation", seeds, 5)
    assert "What is 2+2?" in prompt
    assert "5 NEW rows" in prompt


def test_build_generation_prompt_adversarial_mentions_edge_cases():
    seeds = [SimpleNamespace(input="What is 2+2?", expected_output="4")]
    prompt = build_generation_prompt("adversarial", seeds, 3)
    assert "adversarial" in prompt.lower()


@patch("services.synthetic_service.completion")
def test_generate_rows_calls_model_and_parses_response(mock_completion):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='[{"input": "q1", "expected_output": "a1"}]'))]
    mock_completion.return_value = mock_response

    seeds = [SimpleNamespace(input="seed", expected_output="seed answer")]
    rows = generate_rows(model="ollama/llama3", mode="variation", seed_rows=seeds, count=1)

    assert rows == [{"input": "q1", "expected_output": "a1", "context": None, "tags": {"synthetic": True}}]
    mock_completion.assert_called_once()
