from evaluators.base import Evaluator
from evaluators.llm_judge import ask_judge

PROMPT = """You are evaluating faithfulness of an AI answer to its provided context (RAG groundedness).
Faithfulness means every claim in the answer is supported by the context, with no fabricated information.

Context:
{context}

Answer:
{output}

Respond with ONLY a JSON object: {{"score": <float 0-1>, "reason": "<short reason>"}}
1.0 = fully grounded in context, 0.0 = entirely unsupported/fabricated.
"""


class FaithfulnessEvaluator(Evaluator):
    name = "faithfulness"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not context:
            return 1.0
        prompt = PROMPT.format(context=context, output=output)
        return ask_judge(judge_model, prompt)
