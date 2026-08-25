"""Patches an existing `openai.OpenAI` client instance so every
`chat.completions.create` call is traced, without changing call sites.

Usage:
    import openai
    from sdk.client import OpenEvalClient
    from sdk.integrations.openai import patch_openai_client

    client = openai.OpenAI()
    patch_openai_client(client, OpenEvalClient(api_key="oe_..."))

    client.chat.completions.create(model="gpt-4o-mini", messages=[...])  # now traced
"""

import functools
import time


def patch_openai_client(openai_client, openeval_client) -> None:
    original_create = openai_client.chat.completions.create

    @functools.wraps(original_create)
    def traced_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        prompt = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        start = time.perf_counter()
        error = None
        response = None
        try:
            response = original_create(*args, **kwargs)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            output_text = ""
            prompt_tokens = completion_tokens = 0
            if response is not None:
                output_text = response.choices[0].message.content or ""
                if response.usage:
                    prompt_tokens = response.usage.prompt_tokens
                    completion_tokens = response.usage.completion_tokens
            openeval_client._log_trace(
                model=model,
                prompt=prompt,
                response=output_text,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=0.0,  # OpenAI SDK doesn't return pricing - use sdk.client.OpenEvalClient.completion (via LiteLLM) for cost tracking
                tags={},
                error=error,
            )

    openai_client.chat.completions.create = traced_create
