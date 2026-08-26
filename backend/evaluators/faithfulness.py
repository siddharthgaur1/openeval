from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from evaluators.base import Evaluator, split_context
from evaluators.deepeval_llm import LiteLLMDeepEvalModel


class FaithfulnessEvaluator(Evaluator):
    """RAG groundedness: does every claim in the answer trace back to the retrieved
    context? Backed by DeepEval's FaithfulnessMetric (claim extraction + verdict per
    claim), not a hand-rolled prompt.
    """

    name = "faithfulness"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        chunks = split_context(context)
        if not chunks:
            return 1.0
        metric = FaithfulnessMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output, retrieval_context=chunks)
        return metric.measure(test_case)
