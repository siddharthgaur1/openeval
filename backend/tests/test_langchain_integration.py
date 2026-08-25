from unittest.mock import MagicMock
from uuid import uuid4

import pytest

langchain_core = pytest.importorskip("langchain_core", reason="langchain-core is an optional SDK integration dependency")

from sdk.integrations.langchain import OpenEvalCallbackHandler  # noqa: E402


def _fake_llm_result(text="hi", model="gpt-4o-mini", prompt_tokens=5, completion_tokens=3):
    generation = MagicMock(text=text)
    result = MagicMock()
    result.generations = [[generation]]
    result.llm_output = {"model_name": model, "token_usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}
    return result


def test_on_llm_end_logs_trace_with_latency_and_tokens():
    client = MagicMock()
    handler = OpenEvalCallbackHandler(client, tags={"env": "test"})
    run_id = uuid4()

    handler.on_llm_start({}, ["hello"], run_id=run_id)
    handler.on_llm_end(_fake_llm_result(), run_id=run_id)

    client._log_trace.assert_called_once()
    _, kwargs = client._log_trace.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["response"] == "hi"
    assert kwargs["prompt_tokens"] == 5
    assert kwargs["tags"]["env"] == "test"
    assert kwargs["tags"]["parent_run_id"] is None


def test_on_llm_end_records_parent_run_id_for_chained_calls():
    client = MagicMock()
    handler = OpenEvalCallbackHandler(client)
    run_id, parent_id = uuid4(), uuid4()

    handler.on_llm_start({}, ["hello"], run_id=run_id, parent_run_id=parent_id)
    handler.on_llm_end(_fake_llm_result(), run_id=run_id, parent_run_id=parent_id)

    _, kwargs = client._log_trace.call_args
    assert kwargs["tags"]["parent_run_id"] == str(parent_id)


def test_on_llm_error_logs_error_trace():
    client = MagicMock()
    handler = OpenEvalCallbackHandler(client)
    run_id = uuid4()

    handler.on_llm_start({}, ["hello"], run_id=run_id)
    handler.on_llm_error(RuntimeError("boom"), run_id=run_id)

    _, kwargs = client._log_trace.call_args
    assert kwargs["error"] == "boom"
