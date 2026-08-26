from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

from evaluators.base import Evaluator, split_context
from evaluators.deepeval_llm import LiteLLMDeepEvalModel


class HallucinationEvaluator(Evaluator):
    """Does the answer contradict or invent facts beyond the known source documents
    (context, or the expected/reference answer when no context is retrieved)?
    Backed by DeepEval's HallucinationMetric.
    """

    name = "hallucination"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        documents = split_context(context) or ([expected_output] if expected_output else [])
        if not documents:
            return 0.0
        metric = HallucinationMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output, context=documents)
        return metric.measure(test_case)
