from evaluators.deterministic_extra import BleuEvaluator, JsonValidityEvaluator, RegexMatchEvaluator, RougeLEvaluator
from evaluators.exact_match import ExactMatchEvaluator, F1Evaluator
from evaluators.faithfulness import FaithfulnessEvaluator
from evaluators.hallucination import HallucinationEvaluator
from evaluators.relevance import AnswerRelevanceEvaluator
from evaluators.semantic_similarity import SemanticSimilarityEvaluator

REGISTRY = {
    e.name: e
    for e in [
        ExactMatchEvaluator(),
        F1Evaluator(),
        FaithfulnessEvaluator(),
        AnswerRelevanceEvaluator(),
        HallucinationEvaluator(),
        SemanticSimilarityEvaluator(),
        JsonValidityEvaluator(),
        RegexMatchEvaluator(),
        BleuEvaluator(),
        RougeLEvaluator(),
    ]
}


def get_evaluator(name: str):
    if name not in REGISTRY:
        raise KeyError(f"Unknown metric: {name}. Available: {list(REGISTRY)}")
    return REGISTRY[name]
