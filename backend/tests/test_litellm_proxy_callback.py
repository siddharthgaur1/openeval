"""Tests infra/litellm-proxy/callback.py by importing it directly from that
directory (it's not a backend package - it ships inside the standalone proxy
image), mocking httpx so no network call happens.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

CALLBACK_PATH = Path(__file__).parent.parent.parent / "infra" / "litellm-proxy" / "callback.py"


def _load_callback_module(monkeypatch):
    monkeypatch.setenv("OPENEVAL_API_KEY", "oe_test_key")
    monkeypatch.setenv("OPENEVAL_API_URL", "http://backend:8000")
    spec = importlib.util.spec_from_file_location("openeval_litellm_callback", CALLBACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["openeval_litellm_callback"] = module
    spec.loader.exec_module(module)
    return module


def test_logs_success_event_posts_expected_payload(monkeypatch):
    module = _load_callback_module(monkeypatch)

    response_obj = MagicMock()
    response_obj.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    response_obj.choices = [MagicMock(message=MagicMock(content="hi there"))]

    with patch.object(module.httpx, "post") as mock_post:
        module.openeval_handler.log_success_event(
            kwargs={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}], "response_cost": 0.002, "litellm_params": {}},
            response_obj=response_obj,
            start_time=0.0,
            end_time=0.5,
        )

    mock_post.assert_called_once()
    _, call_kwargs = mock_post.call_args
    payload = call_kwargs["json"]
    assert payload["model"] == "gpt-4o-mini"
    assert payload["response"] == "hi there"
    assert payload["prompt_tokens"] == 10
    assert payload["completion_tokens"] == 5
    assert payload["cost_usd"] == 0.002
    assert call_kwargs["headers"]["Authorization"] == "Bearer oe_test_key"


def test_no_op_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENEVAL_API_KEY", raising=False)
    module = _load_callback_module(monkeypatch)
    module.OPENEVAL_API_KEY = ""

    with patch.object(module.httpx, "post") as mock_post:
        module.openeval_handler.log_success_event(kwargs={"model": "x", "messages": []}, response_obj=None, start_time=0.0, end_time=0.1)

    mock_post.assert_not_called()
