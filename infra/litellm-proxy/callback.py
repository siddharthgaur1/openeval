"""LiteLLM proxy callback that logs every request/response to OpenEval - this is what
gives "zero-code tracing": point any OpenAI-compatible client at the LiteLLM proxy
(instead of directly at openai.com) and every call is traced without touching app code.

Registered via litellm_config.yaml: `litellm_settings.callbacks: ["callback.openeval_handler"]`.
"""

import os
import time

import httpx
from litellm.integrations.custom_logger import CustomLogger

OPENEVAL_API_URL = os.environ.get("OPENEVAL_API_URL", "http://backend:8000")
OPENEVAL_API_KEY = os.environ.get("OPENEVAL_API_KEY", "")
# Optional - omit to trace into the API key owner's default project server-side.
OPENEVAL_PROJECT_ID = os.environ.get("OPENEVAL_PROJECT_ID") or None


class OpenEvalLogger(CustomLogger):
    def _log(self, kwargs: dict, response_obj, start_time: float, end_time: float, error: str | None = None) -> None:
        if not OPENEVAL_API_KEY:
            return  # tracing is opt-in - no key configured means no-op, not a crash

        messages = kwargs.get("messages", [])
        prompt = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        usage = getattr(response_obj, "usage", None) if response_obj else None
        output_text = ""
        if response_obj and getattr(response_obj, "choices", None):
            output_text = response_obj.choices[0].message.content or ""

        payload = {
            "project_id": OPENEVAL_PROJECT_ID,
            "name": "litellm-proxy-call",
            "model": kwargs.get("model", "unknown"),
            "prompt": prompt,
            "response": output_text,
            "latency_ms": (end_time - start_time) * 1000,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "cost_usd": kwargs.get("response_cost", 0) or 0,
            "tags": kwargs.get("litellm_params", {}).get("metadata", {}).get("tags", {}),
            "error": error,
        }
        try:
            httpx.post(
                f"{OPENEVAL_API_URL}/api/traces",
                json=payload,
                headers={"Authorization": f"Bearer {OPENEVAL_API_KEY}"},
                timeout=5.0,
            )
        except httpx.HTTPError:
            pass  # tracing must never break the proxied call

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._log(kwargs, response_obj, start_time, end_time)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._log(kwargs, response_obj, start_time, end_time, error=str(kwargs.get("exception", "unknown error")))


openeval_handler = OpenEvalLogger()
