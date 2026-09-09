import json

from evaluators import get_evaluator
from evaluators.trajectory import (
    TrajectoryBudgetAdherenceEvaluator,
    TrajectoryErrorRecoveryEvaluator,
    TrajectoryLoopDetectionEvaluator,
    TrajectoryStepEfficiencyEvaluator,
    TrajectoryTaskCompletionEvaluator,
    TrajectoryToolSelectionEvaluator,
)


def call(step_type, tool_name, tool_input=None, error=None):
    return {"step_type": step_type, "tool_name": tool_name, "tool_input": tool_input or {}, "error": error}


def traj(steps, **kwargs):
    return json.dumps({"steps": steps, "terminal_state": "completed", **kwargs})


def spec(**kwargs):
    return json.dumps(kwargs)


def score(evaluator, output, expected_output=None):
    return evaluator.score(input="task", output=output, expected_output=expected_output, context=None, judge_model="x")


# --- task completion ---


def test_task_completion_acceptable_state_no_assertions():
    assert score(TrajectoryTaskCompletionEvaluator(), traj([])) == 1.0


def test_task_completion_unacceptable_state_no_assertions():
    out = traj([], terminal_state="failed")
    assert score(TrajectoryTaskCompletionEvaluator(), out) == 0.0


def test_task_completion_escalated_when_declared_acceptable():
    out = traj([], terminal_state="escalated")
    s = spec(acceptable_terminal_states=["escalated"])
    assert score(TrajectoryTaskCompletionEvaluator(), out, s) == 1.0


def test_task_completion_splits_state_and_assertions():
    out = traj([call("tool_call", "search")], final_output="the answer")
    s = spec(success_assertions=[{"tool_called": "search"}, {"output_contains": "missing"}])
    # terminal ok (0.4) + half the assertions (0.6 * 0.5)
    assert score(TrajectoryTaskCompletionEvaluator(), out, s) == 0.7


def test_task_completion_assertion_reads_metadata():
    out = traj([], metadata={"metrics": {"roc_auc": 0.9}})
    s = spec(success_assertions=[{"metric_present": "roc_auc"}])
    assert score(TrajectoryTaskCompletionEvaluator(), out, s) == 1.0


def test_task_completion_malformed_trajectory_is_zero():
    assert score(TrajectoryTaskCompletionEvaluator(), "not json") == 0.0


# --- tool selection ---


def test_tool_selection_no_expected_tools_is_one():
    assert score(TrajectoryToolSelectionEvaluator(), traj([call("tool_call", "anything")])) == 1.0


def test_tool_selection_perfect_match():
    out = traj([call("tool_call", "search"), call("tool_call", "summarize")])
    s = spec(expected_tools=["search", "summarize"])
    assert score(TrajectoryToolSelectionEvaluator(), out, s) == 1.0


def test_tool_selection_partial_is_between():
    out = traj([call("tool_call", "search"), call("tool_call", "unrelated")])
    s = spec(expected_tools=["search", "summarize"])
    assert 0 < score(TrajectoryToolSelectionEvaluator(), out, s) < 1


def test_tool_selection_forbidden_tool_halves_score():
    out = traj([call("tool_call", "search"), call("tool_call", "delete_prod")])
    s = spec(expected_tools=["search"], forbidden_tools=["delete_prod"])
    clean = traj([call("tool_call", "search"), call("tool_call", "delete_prod")])
    without = score(TrajectoryToolSelectionEvaluator(), clean, spec(expected_tools=["search"]))
    assert score(TrajectoryToolSelectionEvaluator(), out, s) == without * 0.5


# --- step efficiency ---


def test_step_efficiency_at_optimum_is_one():
    out = traj([call("tool_call", "a"), call("tool_call", "b")])
    assert score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=2)) == 1.0


def test_step_efficiency_under_optimum_is_not_rewarded():
    out = traj([call("tool_call", "a")])
    assert score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=4)) == 1.0


def test_step_efficiency_double_optimum_is_zero():
    out = traj([call("tool_call", f"t{i}") for i in range(4)])
    assert score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=2)) == 0.0


def test_step_efficiency_no_tool_calls_is_zero():
    out = traj([{"step_type": "llm_message"}])
    assert score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=2)) == 0.0


def test_step_efficiency_ignores_non_tool_call_steps():
    out = traj([call("tool_call", "a"), call("tool_result", "a"), call("tool_call", "b"), call("tool_result", "b")])
    assert score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=2)) == 1.0


# --- error recovery ---


def test_error_recovery_no_failures_is_one():
    assert score(TrajectoryErrorRecoveryEvaluator(), traj([call("tool_call", "a")])) == 1.0


def test_error_recovery_retry_then_success_is_recovered():
    out = traj([
        call("tool_result", "search", error="timeout"),
        call("tool_call", "search"),
        call("tool_result", "search"),
    ])
    assert score(TrajectoryErrorRecoveryEvaluator(), out) == 1.0


def test_error_recovery_failure_at_end_is_gave_up():
    out = traj([call("tool_call", "search"), call("tool_result", "search", error="boom")], terminal_state="failed")
    assert score(TrajectoryErrorRecoveryEvaluator(), out) == 0.0


def test_error_recovery_endless_retries_of_same_call_is_looped():
    out = traj(
        [call("tool_result", "search", error="boom") for _ in range(4)],
        terminal_state="failed",
    )
    # every failure sees only further failures on the same tool
    assert score(TrajectoryErrorRecoveryEvaluator(), out) < 0.5


def test_error_recovery_routing_around_failure_is_partial():
    out = traj([
        call("tool_result", "search", error="boom"),
        call("tool_call", "other"),
        call("tool_result", "other"),
    ])
    assert score(TrajectoryErrorRecoveryEvaluator(), out) == 0.6


# --- budget adherence ---


def test_budget_no_caps_declared_is_one():
    assert score(TrajectoryBudgetAdherenceEvaluator(), traj([], total_tokens=999999)) == 1.0


def test_budget_within_cap_is_one():
    out = traj([], total_tokens=500)
    assert score(TrajectoryBudgetAdherenceEvaluator(), out, spec(budget={"max_tokens": 1000})) == 1.0


def test_budget_double_cap_is_zero():
    out = traj([], total_tokens=2000)
    assert score(TrajectoryBudgetAdherenceEvaluator(), out, spec(budget={"max_tokens": 1000})) == 0.0


def test_budget_averages_declared_axes_only():
    out = traj([], total_tokens=1500, wall_clock_seconds=1.0)
    s = spec(budget={"max_tokens": 1000, "max_seconds": 10})
    # tokens at 1.5x -> 0.5, seconds under cap -> 1.0
    assert score(TrajectoryBudgetAdherenceEvaluator(), out, s) == 0.75


def test_budget_exceeded_terminal_state_caps_score():
    out = traj([], total_tokens=100, terminal_state="budget_exceeded")
    assert score(TrajectoryBudgetAdherenceEvaluator(), out, spec(budget={"max_tokens": 1000})) == 0.5


# --- loop detection ---


def test_loop_detection_no_repeats_is_one():
    out = traj([call("tool_call", "a", {"q": 1}), call("tool_call", "a", {"q": 2})])
    assert score(TrajectoryLoopDetectionEvaluator(), out) == 1.0


def test_loop_detection_same_tool_different_input_is_not_a_loop():
    out = traj([call("tool_call", "a", {"q": i}) for i in range(5)])
    assert score(TrajectoryLoopDetectionEvaluator(), out) == 1.0


def test_loop_detection_identical_calls_penalized():
    out = traj([call("tool_call", "a", {"q": 1}) for _ in range(4)])
    assert score(TrajectoryLoopDetectionEvaluator(), out) == 0.0


def test_loop_detection_partial_loop_is_between():
    steps = [call("tool_call", "a", {"q": 1}) for _ in range(3)]
    steps += [call("tool_call", f"t{i}") for i in range(6)]
    assert 0 < score(TrajectoryLoopDetectionEvaluator(), traj(steps)) < 1


# --- registry wiring ---


def test_trajectory_metrics_are_registered():
    for name in [
        "trajectory_task_completion",
        "trajectory_tool_selection",
        "trajectory_step_efficiency",
        "trajectory_error_recovery",
        "trajectory_budget_adherence",
        "trajectory_loop_detection",
        "trajectory_reasoning",
    ]:
        assert get_evaluator(name).name == name


# --- reasoning / evidence (the widened contract) ---


def test_step_efficiency_evidence_points_at_the_steps_past_optimal():
    out = traj([call("tool_call", "s") for _ in range(4)])
    result = score(TrajectoryStepEfficiencyEvaluator(), out, spec(optimal_steps=2))
    assert result == 0.0
    assert result.evidence == [2, 3]
    assert "optimal 2" in result.reasoning
    assert result.details["actual_steps"] == 4


def test_loop_detection_evidence_lists_the_repeated_steps():
    steps = [call("tool_call", "search", {"q": "x"}) for _ in range(3)] + [call("tool_call", "done")]
    result = score(TrajectoryLoopDetectionEvaluator(), traj(steps))
    assert result.evidence == [0, 1, 2]
    assert result.details["loops"][0] == {"tool": "search", "count": 3, "steps": [0, 1, 2]}


def test_tool_selection_evidence_flags_forbidden_calls():
    steps = [call("tool_call", "search"), call("tool_call", "rm_rf")]
    result = score(TrajectoryToolSelectionEvaluator(), traj(steps), spec(expected_tools=["search"], forbidden_tools=["rm_rf"]))
    assert result.evidence == [1]
    assert "forbidden" in result.reasoning


def test_error_recovery_evidence_skips_clean_recoveries():
    steps = [
        call("tool_call", "a", error="boom"),
        call("tool_result", "a"),
        call("tool_call", "b", error="boom"),
    ]
    result = score(TrajectoryErrorRecoveryEvaluator(), traj(steps))
    assert result.evidence == [2]  # step 0 recovered; step 2 never did


def test_bare_float_metrics_carry_no_reasoning():
    from evaluators.base import explain

    assert explain(get_evaluator("exact_match").score(
        input="q", output="a", expected_output="a", context=None, judge_model="x")) is None
