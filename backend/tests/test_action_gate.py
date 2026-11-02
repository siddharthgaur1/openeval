"""The run-eval action's gate: what makes a pull request fail."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/actions/run-eval/check_thresholds.py"
spec = importlib.util.spec_from_file_location("check_thresholds", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def run(tmp_path, scores, thresholds, status="completed"):
    path = tmp_path / "eval_result.json"
    path.write_text(json.dumps({"status": status, "summary": {"avg_scores": scores}}))
    return gate.main(str(path), thresholds)


def test_passes_when_scores_meet_thresholds(tmp_path):
    assert run(tmp_path, {"f1": 0.9, "hallucination": 0.1}, "f1>=0.8,hallucination<=0.2") == 0


def test_score_equal_to_the_threshold_passes(tmp_path):
    assert run(tmp_path, {"f1": 0.8}, "f1>=0.8") == 0


def test_fails_when_a_higher_is_better_score_drops(tmp_path, capsys):
    assert run(tmp_path, {"f1": 0.5}, "f1>=0.8") == 1
    assert "f1: 0.500" in capsys.readouterr().out


def test_fails_when_a_lower_is_better_score_rises(tmp_path):
    assert run(tmp_path, {"hallucination": 0.4}, "hallucination<=0.2") == 1


def test_missing_metric_fails_rather_than_passing_silently(tmp_path):
    assert run(tmp_path, {"f1": 0.9}, "faithfulness>=0.8") == 1


def test_failed_run_fails_even_without_thresholds(tmp_path):
    assert run(tmp_path, {}, "", status="failed") == 1


def test_no_thresholds_only_requires_a_completed_run(tmp_path):
    assert run(tmp_path, {"f1": 0.1}, "") == 0


def test_malformed_threshold_is_an_error_not_a_pass(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, {"f1": 0.9}, "f1=0.8")
