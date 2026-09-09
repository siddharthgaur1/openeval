from abc import ABC, abstractmethod


class ScoreResult(float):
    """A score that also carries *why*.

    Subclasses ``float`` deliberately: every existing consumer (``summarize_run``
    averages, ``compare_runs`` deltas, JSON serialisation, ``== 1.0`` in tests)
    keeps working on it unchanged, so evaluators can be upgraded one at a time
    instead of all 23 at once. Evaluators that return a plain float stay valid.

    - ``reasoning``: one sentence saying what cost (or earned) the score.
    - ``evidence``: indices into the trajectory/step list that caused it.
    - ``details``: any extra structured numbers worth showing.
    """

    reasoning: str | None
    evidence: list[int]
    details: dict

    def __new__(cls, score: float, reasoning: str | None = None, evidence=None, details=None):
        self = super().__new__(cls, score)
        self.reasoning = reasoning
        self.evidence = list(evidence or [])
        self.details = dict(details or {})
        return self


def explain(value) -> dict | None:
    """The explanation attached to a score, or None for a bare float."""
    if not isinstance(value, ScoreResult) or not (value.reasoning or value.evidence or value.details):
        return None
    return {"reasoning": value.reasoning, "evidence": value.evidence, "details": value.details}


class Evaluator(ABC):
    name: str

    @abstractmethod
    def score(self, *, input: str, output: str, expected_output: str | None, context: str | None, judge_model: str) -> float:
        """Return a score in [0, 1], or a `ScoreResult` to also explain it."""
        raise NotImplementedError


def split_context(context: str | None) -> list[str]:
    """DatasetRow.context is a single text field; RAG metrics (DeepEval/RAGAS) expect
    a list of retrieved chunks. A row with multiple chunks separates them with a
    "\n---\n" line; otherwise the whole field is treated as one chunk.
    """
    if not context:
        return []
    return [c.strip() for c in context.split("\n---\n") if c.strip()]
