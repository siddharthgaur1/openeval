"""OpenEval Python SDK.

Usage:
    from openeval import OpenEvalClient

    client = OpenEvalClient(api_key="oe_...", base_url="http://localhost:8000")
    response = client.completion(model="gpt-4o-mini", messages=[...], tags={"env": "prod"})
"""

import functools
import time
from typing import Any

import httpx
from litellm import completion, completion_cost


class OpenEvalClient:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000", timeout: float = 5.0, project_id: str | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Omit to trace into the caller's default (personal) project server-side.
        self.project_id = project_id

    def _log_trace(self, *, model: str, prompt: str, response: str, latency_ms: float, prompt_tokens: int, completion_tokens: int, cost_usd: float, tags: dict, error: str | None = None) -> None:
        payload = {
            "project_id": self.project_id,
            "name": "llm-call",
            "model": model,
            "prompt": prompt,
            "response": response,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "tags": tags,
            "error": error,
        }
        try:
            httpx.post(
                f"{self.base_url}/api/traces",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError:
            # Tracing must never break the caller's LLM call.
            pass

    def completion(self, model: str, messages: list[dict[str, Any]], tags: dict | None = None, **kwargs) -> Any:
        """Drop-in wrapper around litellm.completion() that also logs a trace."""
        tags = tags or {}
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        start = time.perf_counter()
        error = None
        response = None
        try:
            response = completion(model=model, messages=messages, **kwargs)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            output_text = ""
            prompt_tokens = completion_tokens = 0
            cost_usd = 0.0
            if response is not None:
                output_text = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0)
                    completion_tokens = getattr(usage, "completion_tokens", 0)
                try:
                    cost_usd = completion_cost(completion_response=response)
                except Exception:
                    cost_usd = 0.0
            self._log_trace(
                model=model,
                prompt=prompt,
                response=output_text,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                tags=tags,
                error=error,
            )


def track(client: OpenEvalClient, tags: dict | None = None):
    """Decorator form: wraps any function that calls litellm.completion internally
    is NOT auto-instrumented by this decorator (use client.completion for that);
    this decorator just times the call and logs a trace around its return value
    when the function returns a litellm-style response object.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            try:
                output_text = result.choices[0].message.content or ""
                model = result.model
                usage = getattr(result, "usage", None)
                prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
                completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
                cost_usd = completion_cost(completion_response=result)
            except (AttributeError, IndexError):
                return result
            client._log_trace(
                model=model,
                prompt="",
                response=output_text,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                tags=tags or {},
            )
            return result

        return wrapper

    return decorator
