import json
import re

from evaluators.base import Evaluator
from evaluators.exact_match import _normalize


class JsonValidityEvaluator(Evaluator):
    name = "json_validity"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        try:
            json.loads(output)
            return 1.0
        except (json.JSONDecodeError, TypeError):
            return 0.0


class RegexMatchEvaluator(Evaluator):
    """expected_output is treated as the regex pattern to match against output."""

    name = "regex_match"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not expected_output:
            return 0.0
        try:
            return 1.0 if re.search(expected_output, output) else 0.0
        except re.error:
            return 0.0


def _ngrams(tokens: list[str], n: int) -> list[tuple]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


class BleuEvaluator(Evaluator):
    """Simplified corpus-free BLEU (up to 4-gram precision, brevity penalty), single reference."""

    name = "bleu"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not expected_output:
            return 0.0
        candidate = _normalize(output).split()
        reference = _normalize(expected_output).split()
        if not candidate or not reference:
            return 0.0

        precisions = []
        for n in range(1, 5):
            cand_ngrams = _ngrams(candidate, n)
            ref_ngrams = _ngrams(reference, n)
            if not cand_ngrams:
                precisions.append(0.0)
                continue
            ref_counts: dict = {}
            for g in ref_ngrams:
                ref_counts[g] = ref_counts.get(g, 0) + 1
            matches = 0
            for g in cand_ngrams:
                if ref_counts.get(g, 0) > 0:
                    matches += 1
                    ref_counts[g] -= 1
            precisions.append(matches / len(cand_ngrams))

        if any(p == 0 for p in precisions):
            return 0.0

        import math

        geo_mean = math.exp(sum(math.log(p) for p in precisions) / len(precisions))
        brevity_penalty = 1.0 if len(candidate) > len(reference) else math.exp(1 - len(reference) / len(candidate))
        return max(0.0, min(1.0, geo_mean * brevity_penalty))


class RougeLEvaluator(Evaluator):
    """ROUGE-L F1 based on longest common subsequence."""

    name = "rouge_l"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        if not expected_output:
            return 0.0
        candidate = _normalize(output).split()
        reference = _normalize(expected_output).split()
        if not candidate or not reference:
            return 0.0

        lcs = _lcs_length(candidate, reference)
        if lcs == 0:
            return 0.0
        precision = lcs / len(candidate)
        recall = lcs / len(reference)
        return 2 * precision * recall / (precision + recall)


def _lcs_length(a: list[str], b: list[str]) -> int:
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]
