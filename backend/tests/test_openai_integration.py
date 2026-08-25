from unittest.mock import MagicMock

from sdk.integrations.openai import patch_openai_client


def test_patch_openai_client_logs_trace_on_success():
    fake_openai_client = MagicMock()
    original_response = MagicMock()
    original_response.choices = [MagicMock(message=MagicMock(content="hello back"))]
    original_response.usage = MagicMock(prompt_tokens=3, completion_tokens=2)
    fake_openai_client.chat.completions.create.return_value = original_response

    openeval_client = MagicMock()
    patch_openai_client(fake_openai_client, openeval_client)

    result = fake_openai_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert result is original_response
    openeval_client._log_trace.assert_called_once()
    _, call_kwargs = openeval_client._log_trace.call_args
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["response"] == "hello back"
    assert call_kwargs["prompt_tokens"] == 3
    assert call_kwargs["error"] is None


def test_patch_openai_client_logs_trace_on_error():
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.side_effect = RuntimeError("boom")

    openeval_client = MagicMock()
    patch_openai_client(fake_openai_client, openeval_client)

    try:
        fake_openai_client.chat.completions.create(model="gpt-4o-mini", messages=[])
    except RuntimeError:
        pass

    openeval_client._log_trace.assert_called_once()
    _, call_kwargs = openeval_client._log_trace.call_args
    assert call_kwargs["error"] == "boom"
