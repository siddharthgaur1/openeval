from evaluators.base import Evaluator
from evaluators.llm_judge import ask_judge

PROMPT = """You are evaluating how relevant an AI answer is to the question asked.

Question:
{input}

Answer:
{output}

Respond with ONLY a JSON object: {{"score": <float 0-1>, "reason": "<short reason>"}}
1.0 = directly and completely answers the question, 0.0 = off-topic or non-responsive.
"""


class AnswerRelevanceEvaluator(Evaluator):
    name = "answer_relevance"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        prompt = PROMPT.format(input=input, output=output)
        return ask_judge(judge_model, prompt)
