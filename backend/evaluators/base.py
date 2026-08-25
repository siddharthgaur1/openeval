from abc import ABC, abstractmethod


class Evaluator(ABC):
    name: str

    @abstractmethod
    def score(self, *, input: str, output: str, expected_output: str | None, context: str | None, judge_model: str) -> float:
        """Return a score in [0, 1]."""
        raise NotImplementedError
