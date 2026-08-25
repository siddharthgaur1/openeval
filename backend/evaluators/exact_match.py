from evaluators.base import Evaluator


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


class ExactMatchEvaluator(Evaluator):
    name = "exact_match"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if expected_output is None:
            return 0.0
        return 1.0 if _normalize(output) == _normalize(expected_output) else 0.0


class F1Evaluator(Evaluator):
    name = "f1"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if expected_output is None:
            return 0.0
        pred_tokens = _normalize(output).split()
        gold_tokens = _normalize(expected_output).split()
        if not pred_tokens or not gold_tokens:
            return 0.0
        common = {}
        for tok in pred_tokens:
            common[tok] = min(pred_tokens.count(tok), gold_tokens.count(tok))
        num_same = sum(common.values())
        if num_same == 0:
            return 0.0
        precision = num_same / len(pred_tokens)
        recall = num_same / len(gold_tokens)
        return 2 * precision * recall / (precision + recall)
