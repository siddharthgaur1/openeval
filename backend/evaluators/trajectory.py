"""Trajectory-level metrics: score the *sequence of steps* an agent took, not just
its final answer.

These follow the same field-reinterpretation precedent as `RegexMatchEvaluator`
(which treats `expected_output` as a regex): here `output` is the agent's recorded
trajectory as JSON, and `expected_output` is the task spec it should be judged
against, also JSON. Both are already Text columns on `DatasetRow` / `EvalResult`,
so no schema change is needed.

output JSON:
    {"steps": [{"step_type": "tool_call", "tool_name": "search",
                "tool_input": {...}, "error": null}, ...],
     "terminal_state": "completed", "final_output": "...",
     "total_tokens": 0, "total_cost_usd": 0.0, "wall_clock_seconds": 0.0,
     "metadata": {"artifacts": [...], "metrics": {...}}}

expected_output JSON (every key optional):
    {"expected_tools": [...], "forbidden_tools": [...], "optimal_steps": 10,
     "budget": {"max_tokens": N, "max_cost_usd": N, "max_seconds": N},
     "acceptable_terminal_states": ["completed"],
     "success_assertions": [{"tool_called": "search"}, ...]}

A malformed or missing trajectory scores 0.0, matching how the other
deterministic evaluators handle unusable input.
"""

import json

from evaluators.base import Evaluator

# ponytail: fixed threshold, matching the harness default. Make it a task-spec
# field if anyone actually needs to tune it per task.
LOOP_REPEAT_LIMIT = 3

# Terminal states that count as the agent having gotten somewhere on its own.
_OK_STATES = {"completed", "escalated"}


def parse_trajectory(output: str | None) -> dict | None:
    """Trajectory JSON as a dict, or None when it is missing/unusable."""
    try:
        traj = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(traj, dict) or not isinstance(traj.get("steps"), list):
        return None
    return traj


def parse_spec(expected_output: str | None) -> dict:
    """Task spec as a dict; an absent or unusable spec is an empty spec."""
    try:
        spec = json.loads(expected_output)
    except (json.JSONDecodeError, TypeError):
        return {}
    return spec if isinstance(spec, dict) else {}


def _tool_calls(traj: dict) -> list[dict]:
    return [s for s in traj["steps"] if s.get("step_type") == "tool_call" and s.get("tool_name")]


def _tools_used(traj: dict) -> list[str]:
    return [s["tool_name"] for s in traj["steps"] if s.get("tool_name")]


def _signature(step: dict) -> str:
    """Stable identity for loop detection: same tool, same input."""
    payload = json.dumps(step.get("tool_input") or {}, sort_keys=True, default=str)
    return f"{step.get('tool_name')}:{payload}"


def _check_assertion(assertion: dict, traj: dict) -> bool:
    """One checkable claim about a finished run. Exactly one key is set."""
    key, value = next(iter(assertion.items()), (None, None))
    if key == "terminal_state":
        return traj.get("terminal_state") == value
    if key == "artifact_exists":
        return any(value in str(a) for a in (traj.get("metadata") or {}).get("artifacts") or [])
    if key == "metric_present":
        return value in ((traj.get("metadata") or {}).get("metrics") or {})
    if key == "output_contains":
        return str(value).lower() in str(traj.get("final_output") or "").lower()
    if key == "tool_called":
        return value in _tools_used(traj)
    if key == "tool_not_called":
        return value not in _tools_used(traj)
    return False


class TrajectoryTaskCompletionEvaluator(Evaluator):
    """Did the run end acceptably and satisfy its declared assertions?

    Split 40/60 between reaching an acceptable terminal state and passing the
    assertions: an agent that stops cleanly but produces nothing is not half
    right, and the assertions are what say so.
    """

    name = "trajectory_task_completion"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0
        spec = parse_spec(expected_output)

        acceptable = spec.get("acceptable_terminal_states") or ["completed"]
        terminal_ok = traj.get("terminal_state") in acceptable

        assertions = spec.get("success_assertions") or []
        if not assertions:
            return float(terminal_ok)

        passed = sum(1 for a in assertions if _check_assertion(a, traj))
        return 0.4 * float(terminal_ok) + 0.6 * (passed / len(assertions))


class TrajectoryToolSelectionEvaluator(Evaluator):
    """F1 of the tools called against the expected set.

    F1 rather than precision or recall alone, so the agent cannot game it either
    by calling every tool or by calling one correct tool and stopping. Forbidden
    tools halve the score: calling a banned tool is a different class of error
    from missing a useful one, so it is multiplicative, not subtractive.
    """

    name = "trajectory_tool_selection"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0
        spec = parse_spec(expected_output)

        expected = set(spec.get("expected_tools") or [])
        if not expected:
            return 1.0  # nothing declared, nothing to get wrong

        used = set(_tools_used(traj))
        hits = len(used & expected)
        precision = hits / len(used) if used else 0.0
        recall = hits / len(expected)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        if used & set(spec.get("forbidden_tools") or []):
            f1 *= 0.5
        return f1


class TrajectoryStepEfficiencyEvaluator(Evaluator):
    """Tool calls made against the task's optimal count.

    Linear decay: at twice the optimal step count the score is 0. Finishing in
    fewer steps than optimal is not rewarded — that usually means skipping work,
    which is task completion's job to notice, not this metric's.
    """

    name = "trajectory_step_efficiency"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0
        actual = len(_tool_calls(traj))
        if actual == 0:
            return 0.0

        optimal = parse_spec(expected_output).get("optimal_steps") or 10
        ratio = actual / optimal
        return 1.0 if ratio <= 1.0 else max(0.0, 2.0 - ratio)


class TrajectoryErrorRecoveryEvaluator(Evaluator):
    """For every failed step, did the agent recover — and how expensively?

    Measures resilience, not reliability: a run with no failures scores 1.0,
    because penalising an agent for never failing would be backwards.
    """

    name = "trajectory_error_recovery"

    _WEIGHTS = {"recovered": 1.0, "recovered_slowly": 0.6, "looped": 0.2, "gave_up": 0.0}

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0

        steps = traj["steps"]
        failures = [(i, s) for i, s in enumerate(steps) if s.get("error")]
        if not failures:
            return 1.0

        outcomes = [self._classify(traj, i, s) for i, s in failures]
        return sum(self._WEIGHTS[o] for o in outcomes) / len(outcomes)

    def _classify(self, traj: dict, position: int, failure: dict) -> str:
        after = traj["steps"][position + 1 :]
        if not after:
            return "gave_up"

        # Only tool_result steps carry an outcome. Counting the tool_call half of
        # a retry pair as "didn't fail" would score an agent that retried the same
        # broken call forever as having recovered every time.
        attempts = 0
        for step in after:
            if step.get("tool_name") != failure.get("tool_name") or step.get("step_type") != "tool_result":
                continue
            attempts += 1
            if not step.get("error"):
                return "recovered" if attempts <= 2 else "recovered_slowly"

        if attempts >= LOOP_REPEAT_LIMIT:
            return "looped"
        # It moved on to other work and still finished: that is routing around the
        # failure, which is a recovery, just not of the same tool.
        if traj.get("terminal_state") in _OK_STATES:
            return "recovered_slowly"
        return "gave_up"


class TrajectoryBudgetAdherenceEvaluator(Evaluator):
    """Tokens, cost and wall clock against the task's declared caps.

    Each declared axis is scored independently and averaged; an axis with no cap
    is skipped rather than scored 1.0, so adding a cap can only make the score
    more informative, never inflate it.
    """

    name = "trajectory_budget_adherence"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0

        budget = parse_spec(expected_output).get("budget") or {}
        axes = [
            (traj.get("total_tokens") or 0, budget.get("max_tokens")),
            (traj.get("total_cost_usd") or 0, budget.get("max_cost_usd")),
            (traj.get("wall_clock_seconds") or 0, budget.get("max_seconds")),
        ]
        declared = [(actual, cap) for actual, cap in axes if cap]
        if not declared:
            return 1.0

        # Under budget is a pass; over budget decays to 0 at twice the cap.
        parts = [1.0 if actual / cap <= 1.0 else max(0.0, 2.0 - actual / cap) for actual, cap in declared]
        score = sum(parts) / len(parts)
        if traj.get("terminal_state") == "budget_exceeded":
            score = min(score, 0.5)
        return score


class TrajectoryLoopDetectionEvaluator(Evaluator):
    """Flags the same tool called with the same input LOOP_REPEAT_LIMIT+ times.

    Distinct from step efficiency: an agent can be inefficient without looping
    (many *different* calls) and can loop while landing near the optimal step
    count. Scored by the share of the run spent looping, not by loop count — one
    40-step loop is worse than four 3-step ones.
    """

    name = "trajectory_loop_detection"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        traj = parse_trajectory(output)
        if traj is None:
            return 0.0

        calls = _tool_calls(traj)
        by_sig: dict[str, int] = {}
        for step in calls:
            sig = _signature(step)
            by_sig[sig] = by_sig.get(sig, 0) + 1

        looped_steps = sum(n for n in by_sig.values() if n >= LOOP_REPEAT_LIMIT)
        if not looped_steps:
            return 1.0
        return max(0.0, 1.0 - (looped_steps / max(len(calls), 1)) * 1.5)


class TrajectoryReasoningEvaluator(Evaluator):
    """LLM-as-judge over the step sequence: were the decisions reasonable *given
    what each step returned*, or did the agent ignore its own tool output?

    Cannot be computed from the trajectory alone, so it goes through the same
    GEval path as `coherence` / `conciseness`.
    """

    name = "trajectory_reasoning"

    def score(self, *, input, output, expected_output, context, judge_model) -> float:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, SingleTurnParams

        from evaluators.deepeval_llm import LiteLLMDeepEvalModel

        traj = parse_trajectory(output)
        if traj is None:
            return 0.0

        metric = GEval(
            name="Trajectory Reasoning",
            model=LiteLLMDeepEvalModel(judge_model),
            async_mode=False,
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            criteria="'actual output' is an agent's recorded step sequence (tool calls, their "
            "results, and errors) for the task in 'input'. Score whether each decision was "
            "reasonable given what the preceding steps returned: did the agent use the "
            "information its tools gave it, adapt when a step failed, and avoid steps that "
            "could not advance the task? 1.0 = every step follows sensibly from the last, "
            "0.0 = the agent ignored its own results or acted at random.",
        )
        test_case = LLMTestCase(input=input, actual_output=json.dumps(traj["steps"], default=str))
        return metric.measure(test_case)
