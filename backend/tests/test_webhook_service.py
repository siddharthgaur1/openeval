from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.webhook_service import build_payload, eval_run_events, sign_payload


def test_sign_payload_is_deterministic_hmac():
    sig1 = sign_payload("secret", b'{"a":1}')
    sig2 = sign_payload("secret", b'{"a":1}')
    sig3 = sign_payload("other-secret", b'{"a":1}')
    assert sig1 == sig2
    assert sig1 != sig3
    assert len(sig1) == 64  # hex sha256


def test_eval_run_events_completed_fires_completed_and_passed():
    run = SimpleNamespace(status="completed")
    assert set(eval_run_events(run)) == {"eval.completed", "eval.passed"}


def test_eval_run_events_failed_fires_only_completed():
    run = SimpleNamespace(status="failed")
    assert eval_run_events(run) == ["eval.completed"]


def test_eval_run_events_pending_fires_nothing():
    run = SimpleNamespace(status="pending")
    assert eval_run_events(run) == []


def test_build_payload_shape():
    run = SimpleNamespace(id="abc", status="completed", summary={"row_count": 3})
    payload = build_payload("eval.completed", run)
    assert payload == {"event": "eval.completed", "eval_run_id": "abc", "status": "completed", "summary": {"row_count": 3}}


@patch("workers.webhook_tasks.deliver_webhook")
def test_dispatch_regression_webhooks_only_fires_for_regressed_runs(mock_deliver):
    from services.webhook_service import dispatch_regression_webhooks

    webhook = SimpleNamespace(id="wh-1")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id="wh-1", is_active=True, events=["eval.regression_detected"])]

    comparison = {
        "baseline_run_id": "base",
        "runs": [
            {"eval_run_id": "base", "regressions": []},
            {"eval_run_id": "candidate", "regressions": ["exact_match"], "delta_vs_baseline": {"exact_match": -0.4}},
        ],
    }
    dispatch_regression_webhooks(db, "user-1", comparison)
    mock_deliver.delay.assert_called_once()
    args = mock_deliver.delay.call_args[0]
    assert args[0] == "wh-1"
    assert args[1]["eval_run_id"] == "candidate"
