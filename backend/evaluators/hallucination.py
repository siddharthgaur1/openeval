from evaluators.base import Evaluator
from evaluators.llm_judge import ask_judge

PROMPT = """You are detecting hallucination in an AI answer relative to the given context and/or
expected reference answer. A hallucination is a claim not supported by either source.

Context:
{context}

Reference answer (may be empty):
{expected_output}

AI answer:
{output}

Respond with ONLY a JSON object: {{"score": <float 0-1>, "reason": "<short reason>"}}
Score is the HALLUCINATION score: 0.0 = no hallucination (fully supported), 1.0 = entirely hallucinated.
"""


class HallucinationEvaluator(Evaluator):
    name = "hallucination"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not context and not expected_output:
            return 0.0
        prompt = PROMPT.format(
            context=context or "(none)",
            expected_output=expected_output or "(none)",
            output=output,
        )
        return ask_judge(judge_model, prompt)
