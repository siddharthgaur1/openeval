"""RAG context-quality metrics from the original RAGAS metric set.

context_precision / context_recall are backed by DeepEval's ContextualPrecisionMetric /
ContextualRecallMetric (the same algorithms RAGAS implements: LLM-judged relevance/
attribution of each retrieved chunk against the expected answer).

context_entity_recall and noise_robustness have no DeepEval equivalent (they're
RAGAS-specific), and real `ragas` cannot be installed alongside this project's pinned
litellm/instructor (which require openai>=2) — ragas 0.4.x hard-imports
`langchain_community.chat_models.vertexai`, a module removed in langchain-community>=0.4,
so the two dependency trees don't resolve together. These two are implemented instead as
GEval rubrics (DeepEval's LLM-as-judge metric) matching RAGAS's published definitions.
"""

from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evaluators.base import Evaluator, split_context
from evaluators.deepeval_llm import LiteLLMDeepEvalModel


class ContextPrecisionEvaluator(Evaluator):
    name = "context_precision"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        chunks = split_context(context)
        if not chunks or not expected_output:
            return 0.0
        metric = ContextualPrecisionMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output, expected_output=expected_output, retrieval_context=chunks)
        return metric.measure(test_case)


class ContextRecallEvaluator(Evaluator):
    name = "context_recall"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        chunks = split_context(context)
        if not chunks or not expected_output:
            return 0.0
        metric = ContextualRecallMetric(model=LiteLLMDeepEvalModel(judge_model), include_reason=False, async_mode=False)
        test_case = LLMTestCase(input=input, actual_output=output, expected_output=expected_output, retrieval_context=chunks)
        return metric.measure(test_case)


class ContextEntityRecallEvaluator(Evaluator):
    """RAGAS's context_entity_recall: what fraction of the entities in the reference
    answer also appear among the entities in the retrieved context?
    """

    name = "context_entity_recall"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        chunks = split_context(context)
        if not chunks or not expected_output:
            return 0.0
        metric = GEval(
            name="ContextEntityRecall",
            model=LiteLLMDeepEvalModel(judge_model),
            async_mode=False,
            evaluation_params=[SingleTurnParams.EXPECTED_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT],
            criteria=(
                "Identify every named entity (person, place, organization, date, number, etc.) "
                "mentioned in 'expected output'. Score = the fraction of those entities that also "
                "appear (verbatim or as a clear synonym) somewhere in 'retrieval context'. "
                "1.0 = every entity from the expected output is covered by the context, "
                "0.0 = none of them are."
            ),
        )
        test_case = LLMTestCase(input=input, actual_output=output, expected_output=expected_output, retrieval_context=chunks)
        return metric.measure(test_case)


class NoiseRobustnessEvaluator(Evaluator):
    """RAGAS's noise_robustness: does the answer stay correct and avoid being misled
    when the retrieved context contains irrelevant ("noisy") chunks alongside the
    useful ones?
    """

    name = "noise_robustness"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        chunks = split_context(context)
        if not chunks:
            return 1.0
        metric = GEval(
            name="NoiseRobustness",
            model=LiteLLMDeepEvalModel(judge_model),
            async_mode=False,
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT],
            criteria=(
                "'Retrieval context' is a mix of chunks, some relevant to the input question and "
                "some irrelevant/noisy. Score how well 'actual output' ignores the noisy chunks and "
                "answers using only the relevant information. 1.0 = fully robust to noise (correct, "
                "not distracted by irrelevant chunks), 0.0 = clearly misled by irrelevant context "
                "(e.g. includes facts only found in noisy chunks, or gets confused/contradicts itself)."
            ),
        )
        test_case = LLMTestCase(input=input, actual_output=output, retrieval_context=chunks)
        return metric.measure(test_case)
