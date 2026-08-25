"""LangChain (and LangGraph, which runs on the same callback system) integration.

Usage:
    from sdk.client import OpenEvalClient
    from sdk.integrations.langchain import OpenEvalCallbackHandler

    client = OpenEvalClient(api_key="oe_...")
    handler = OpenEvalCallbackHandler(client, tags={"env": "prod"})

    llm.invoke("hello", config={"callbacks": [handler]})
    # or pass callbacks=[handler] when building a LangGraph graph/agent

Every LLM call in the chain/graph is traced, including nested calls (parent_run_id
is recorded in the trace's tags so child calls can be grouped after the fact).
"""

import time
from typing import Any
from uuid import UUID

from sdk.client import OpenEvalClient

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError as exc:  # pragma: no cover - only hit if langchain isn't installed
    raise ImportError("sdk.integrations.langchain requires `pip install langchain-core`") from exc


class OpenEvalCallbackHandler(BaseCallbackHandler):
    def __init__(self, client: OpenEvalClient, tags: dict | None = None):
        self.client = client
        self.base_tags = tags or {}
        self._starts: dict[UUID, tuple[float, list[dict]]] = {}

    def on_llm_start(self, serialized: dict, prompts: list[str], *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        self._starts[run_id] = (time.perf_counter(), [{"role": "user", "content": p} for p in prompts])

    def on_chat_model_start(self, serialized: dict, messages: list[list[Any]], *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        flattened = [{"role": getattr(m, "type", "user"), "content": getattr(m, "content", str(m))} for batch in messages for m in batch]
        self._starts[run_id] = (time.perf_counter(), flattened)

    def on_llm_end(self, response: "LLMResult", *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        start_time, messages = self._starts.pop(run_id, (time.perf_counter(), []))
        latency_ms = (time.perf_counter() - start_time) * 1000
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        output_text = ""
        model = "unknown"
        prompt_tokens = completion_tokens = 0
        cost_usd = 0.0
        if response.generations and response.generations[0]:
            output_text = response.generations[0][0].text or ""
        llm_output = response.llm_output or {}
        model = llm_output.get("model_name", model)
        usage = llm_output.get("token_usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        tags = {**self.base_tags, "parent_run_id": str(parent_run_id) if parent_run_id else None}
        self.client._log_trace(
            model=model,
            prompt=prompt,
            response=output_text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            tags=tags,
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        start_time, messages = self._starts.pop(run_id, (time.perf_counter(), []))
        latency_ms = (time.perf_counter() - start_time) * 1000
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        tags = {**self.base_tags, "parent_run_id": str(parent_run_id) if parent_run_id else None}
        self.client._log_trace(
            model="unknown",
            prompt=prompt,
            response="",
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            tags=tags,
            error=str(error),
        )
