import json
import re

from litellm import completion


def ask_judge(judge_model: str, prompt: str) -> float:
    """Send a scoring prompt to the judge model and parse a 0-1 float from the reply.

    Falls back to 0.0 if the judge doesn't return a parseable score, rather than
    raising and failing the whole eval run.
    """
    response = completion(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = response.choices[0].message.content or ""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            score = float(data.get("score", 0.0))
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    match = re.search(r"([01](?:\.\d+)?)", text)
    if match:
        return max(0.0, min(1.0, float(match.group(1))))
    return 0.0
