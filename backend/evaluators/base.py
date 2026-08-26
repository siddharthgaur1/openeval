from abc import ABC, abstractmethod


class Evaluator(ABC):
    name: str

    @abstractmethod
    def score(self, *, input: str, output: str, expected_output: str | None, context: str | None, judge_model: str) -> float:
        """Return a score in [0, 1]."""
        raise NotImplementedError


def split_context(context: str | None) -> list[str]:
    """DatasetRow.context is a single text field; RAG metrics (DeepEval/RAGAS) expect
    a list of retrieved chunks. A row with multiple chunks separates them with a
    "\\n---\\n" line; otherwise the whole field is treated as one chunk.
    """
    if not context:
        return []
    return [c.strip() for c in context.split("\n---\n") if c.strip()]
