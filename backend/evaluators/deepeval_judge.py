"""LLM-as-judge metrics backed by DeepEval, rather than the hand-rolled prompt+regex
parsing in llm_judge.py — DeepEval's ToxicityMetric/GEval handle prompt construction,
JSON-verdict parsing, and reasoning internally.
"""

from deepeval.metrics import GEval, ToxicityMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evaluators.base import Evaluator
from evaluators.deepeval_llm import LiteLLMDeepEvalModel


class ToxicityEvaluator(Evaluator):
    name = "toxicity"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        metric = ToxicityMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output)
        return metric.measure(test_case)


class CoherenceEvaluator(Evaluator):
    name = "coherence"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        metric = GEval(
            name="Coherence",
            model=LiteLLMDeepEvalModel(judge_model),
            async_mode=False,
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            criteria="Score how logically structured, well-organized, and easy to follow 'actual output' is, "
            "independent of whether it's factually correct. 1.0 = clear and coherent, 0.0 = disjointed or contradictory.",
        )
        test_case = LLMTestCase(input=input, actual_output=output)
        return metric.measure(test_case)


class ConcisenessEvaluator(Evaluator):
    name = "conciseness"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        metric = GEval(
            name="Conciseness",
            model=LiteLLMDeepEvalModel(judge_model),
            async_mode=False,
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            criteria="Score how free 'actual output' is of unnecessary padding, repetition, or irrelevant detail "
            "while still fully answering 'input'. 1.0 = concise and to the point, 0.0 = verbose or rambling.",
        )
        test_case = LLMTestCase(input=input, actual_output=output)
        return metric.measure(test_case)
