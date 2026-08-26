from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

from evaluators.base import Evaluator
from evaluators.deepeval_llm import LiteLLMDeepEvalModel


class AnswerRelevanceEvaluator(Evaluator):
    """How relevant is the answer to the question? Backed by DeepEval's
    AnswerRelevancyMetric (extracts statements from the answer, judges each
    against the question), not a hand-rolled prompt.
    """

    name = "answer_relevance"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        metric = AnswerRelevancyMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output)
        return metric.measure(test_case)
