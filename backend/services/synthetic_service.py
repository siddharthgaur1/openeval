import json
import re

from litellm import completion

VARIATION_PROMPT = """You are generating additional test cases for an LLM evaluation dataset,
based on the seed examples below. Produce {count} NEW rows that are realistic variations of
the seeds - same task/domain, different phrasing, different specifics.

Seed examples:
{seeds}

Respond with ONLY a JSON array of {count} objects, each shaped exactly like:
{{"input": "...", "expected_output": "...", "context": "..."}}
("context" may be an empty string if not applicable.)
"""

ADVERSARIAL_PROMPT = """You are generating adversarial test cases for an LLM evaluation dataset,
based on the seed examples below. Produce {count} NEW rows designed to be edge cases, ambiguous
inputs, or attempts to get an incorrect/unsafe response (e.g. prompt injection, contradictory
instructions, malformed input) - the kind of inputs a robust system must handle gracefully.

Seed examples:
{seeds}

Respond with ONLY a JSON array of {count} objects, each shaped exactly like:
{{"input": "...", "expected_output": "...", "context": "..."}}
("expected_output" should be what a SAFE, correct system would do; "context" may be empty.)
"""


def _format_seeds(seed_rows: list) -> str:
    return "\n".join(f"- input: {r.input!r}, expected_output: {r.expected_output!r}" for r in seed_rows)


def build_generation_prompt(mode: str, seed_rows: list, count: int) -> str:
    template = ADVERSARIAL_PROMPT if mode == "adversarial" else VARIATION_PROMPT
    return template.format(seeds=_format_seeds(seed_rows), count=count)


def generate_rows(model: str, mode: str, seed_rows: list, count: int) -> list[dict]:
    prompt = build_generation_prompt(mode, seed_rows, count)
    response = completion(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.8)
    text = response.choices[0].message.content or ""
    return _parse_rows(text)


def _parse_rows(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [
        {"input": r.get("input", ""), "expected_output": r.get("expected_output"), "context": r.get("context") or None, "tags": {"synthetic": True}}
        for r in rows
        if isinstance(r, dict) and r.get("input")
    ]
