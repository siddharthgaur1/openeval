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

from evaluators.base import Evaluator, ScoreResult

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


def _tool_calls(traj: dict) -> list[tuple[int, dict]]:
    """(index, step) for every tool call, indexed against the full step list so
    the index is usable as evidence a reader can look up."""
    return [(i, s) for i, s in enumerate(traj["steps"]) if s.get("step_type") == "tool_call" and s.get("tool_name")]


def _tools_used(traj: dict) -> list[str]:
    return [s["tool_name"] for s in traj["steps"] if s.get("tool_name")]


def _steps_calling(traj: dict, tools: set) -> list[int]:
    return sorted(i for i, s in enumerate(traj["steps"]) if s.get("tool_name") in tools)


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

        state = traj.get("terminal_state")
        state_note = f"terminal state {state!r} " + ("is acceptable" if terminal_ok else f"is not in {acceptable}")

        assertions = spec.get("success_assertions") or []
        if not assertions:
            return ScoreResult(float(terminal_ok), f"No success assertions declared; {state_note}.",
                               details={"terminal_state": state, "acceptable_terminal_states": acceptable})

        failed = [a for a in assertions if not _check_assertion(a, traj)]
        passed = len(assertions) - len(failed)
        score = 0.4 * float(terminal_ok) + 0.6 * (passed / len(assertions))
        # A failed "tool_not_called" is the one assertion kind that points at real steps.
        banned = {v for a in failed for k, v in a.items() if k == "tool_not_called"}
        return ScoreResult(
            score,
            f"{state_note}; {passed}/{len(assertions)} success assertions passed.",
            evidence=_steps_calling(traj, banned),
            details={"terminal_state": state, "acceptable_terminal_states": acceptable,
                     "failed_assertions": failed},
        )


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
            return ScoreResult(1.0, "No expected_tools declared, so tool choice is unconstrained.")

        used = set(_tools_used(traj))
        hits = len(used & expected)
        precision = hits / len(used) if used else 0.0
        recall = hits / len(expected)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        forbidden_used = used & set(spec.get("forbidden_tools") or [])
        if forbidden_used:
            f1 *= 0.5

        missing = sorted(expected - used)
        unexpected = sorted(used - expected)
        reasons = [f"called {hits}/{len(expected)} expected tools (precision {precision:.2f}, recall {recall:.2f})"]
        if missing:
            reasons.append(f"never called {missing}")
        if unexpected:
            reasons.append(f"called unexpected {unexpected}")
        if forbidden_used:
            reasons.append(f"halved for calling forbidden {sorted(forbidden_used)}")
        return ScoreResult(
            f1,
            "; ".join(reasons) + ".",
            evidence=_steps_calling(traj, forbidden_used | set(unexpected)),
            details={"expected": sorted(expected), "used": sorted(used), "missing": missing,
                     "unexpected": unexpected, "forbidden_used": sorted(forbidden_used),
                     "precision": precision, "recall": recall},
        )


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
        calls = _tool_calls(traj)
        actual = len(calls)
        if actual == 0:
            return ScoreResult(0.0, "The agent made no tool calls at all.")

        optimal = parse_spec(expected_output).get("optimal_steps") or 10
        ratio = actual / optimal
        if ratio <= 1.0:
            return ScoreResult(1.0, f"{actual} tool calls, within the optimal {optimal}.",
                               details={"actual_steps": actual, "optimal_steps": optimal})
        # The calls past the optimal count are exactly what the decay is charging for.
        return ScoreResult(
            max(0.0, 2.0 - ratio),
            f"{actual} tool calls against an optimal {optimal} ({ratio:.2f}x); "
            f"the {actual - optimal} call(s) after the first {optimal} cost the score.",
            evidence=[i for i, _ in calls[optimal:]],
            details={"actual_steps": actual, "optimal_steps": optimal, "ratio": ratio},
        )


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
            return ScoreResult(1.0, "No step failed, so there was nothing to recover from.")

        outcomes = [(i, s, self._classify(traj, i, s)) for i, s in failures]
        score = sum(self._WEIGHTS[o] for _, _, o in outcomes) / len(outcomes)
        tally: dict[str, int] = {}
        for _, _, o in outcomes:
            tally[o] = tally.get(o, 0) + 1
        return ScoreResult(
            score,
            f"{len(failures)} failed step(s): "
            + ", ".join(f"{n} {o.replace(chr(95), chr(32))}" for o, n in sorted(tally.items()))
            + ".",
            # Only the failures that were not cleanly recovered cost anything.
            evidence=[i for i, _, o in outcomes if o != "recovered"],
            details={"failures": [{"step": i, "tool": s.get("tool_name"), "error": s.get("error"), "outcome": o}
                                  for i, s, o in outcomes]},
        )

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
            ("tokens", traj.get("total_tokens") or 0, budget.get("max_tokens")),
            ("cost_usd", traj.get("total_cost_usd") or 0, budget.get("max_cost_usd")),
            ("seconds", traj.get("wall_clock_seconds") or 0, budget.get("max_seconds")),
        ]
        declared = [(axis, actual, cap) for axis, actual, cap in axes if cap]
        if not declared:
            return ScoreResult(1.0, "No budget declared, so nothing could be exceeded.")

        # Under budget is a pass; over budget decays to 0 at twice the cap.
        parts = {axis: (1.0 if actual / cap <= 1.0 else max(0.0, 2.0 - actual / cap)) for axis, actual, cap in declared}
        score = sum(parts.values()) / len(parts)
        capped = traj.get("terminal_state") == "budget_exceeded"
        if capped:
            score = min(score, 0.5)

        over = [f"{axis} {actual} over cap {cap}" for axis, actual, cap in declared if actual > cap]
        if over:
            reason = "Over budget: " + ", ".join(over) + "."
        else:
            reason = ("Within every declared budget: "
                      + ", ".join(f"{axis} {actual}/{cap}" for axis, actual, cap in declared) + ".")
        if capped:
            reason += " Run ended in terminal_state 'budget_exceeded', so the score is capped at 0.5."
        return ScoreResult(
            score, reason,
            details={"axes": [{"axis": a, "actual": v, "cap": c, "score": parts[a]} for a, v, c in declared],
                     "terminal_state_capped": capped},
        )


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
        by_sig: dict[str, list[int]] = {}
        for i, step in calls:
            by_sig.setdefault(_signature(step), []).append(i)

        loops = {sig: idxs for sig, idxs in by_sig.items() if len(idxs) >= LOOP_REPEAT_LIMIT}
        looped_steps = sum(len(idxs) for idxs in loops.values())
        if not looped_steps:
            return ScoreResult(1.0, f"No tool call repeated with identical input {LOOP_REPEAT_LIMIT}+ times.")
        return ScoreResult(
            max(0.0, 1.0 - (looped_steps / max(len(calls), 1)) * 1.5),
            f"{looped_steps} of {len(calls)} tool calls were identical repeats: "
            + ", ".join(f"{sig.split(chr(58), 1)[0]} x{len(idxs)}" for sig, idxs in loops.items())
            + ".",
            evidence=sorted(i for idxs in loops.values() for i in idxs),
            details={"loops": [{"tool": sig.split(":", 1)[0], "count": len(idxs), "steps": idxs}
                               for sig, idxs in loops.items()],
                     "total_tool_calls": len(calls)},
        )


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
        # GEval already produces its own rationale; surface it rather than drop it.
        return ScoreResult(metric.measure(test_case), getattr(metric, "reason", None))
