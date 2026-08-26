import math

from evaluators.base import Evaluator

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticSimilarityEvaluator(Evaluator):
    name = "semantic_similarity"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not expected_output:
            return 0.0
        model = _get_model()
        emb_output, emb_expected = model.encode([output, expected_output])
        similarity = _cosine(emb_output, emb_expected)
        # model.encode() returns numpy arrays, so _cosine's result is numpy.float32 -
        # not JSON-serializable when eval_service persists scores to the DB.
        return float(max(0.0, min(1.0, (similarity + 1) / 2)))
