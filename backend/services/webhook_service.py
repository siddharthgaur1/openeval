import hashlib
import hmac
import json

from sqlalchemy.orm import Session

from models.webhook import Webhook


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def eval_run_events(eval_run) -> list[str]:
    """Which webhook events fire for a completed eval run's final state."""
    events = []
    if eval_run.status == "completed":
        events.append("eval.completed")
        events.append("eval.passed")
    elif eval_run.status == "failed":
        events.append("eval.completed")
    return events


def webhooks_for_event(db: Session, user_id, event: str) -> list[Webhook]:
    hooks = db.query(Webhook).filter(Webhook.user_id == user_id, Webhook.is_active.is_(True)).all()
    return [h for h in hooks if event in h.events]


def build_payload(event: str, eval_run) -> dict:
    return {
        "event": event,
        "eval_run_id": str(eval_run.id),
        "status": eval_run.status,
        "summary": eval_run.summary,
    }


def dispatch_regression_webhooks(db: Session, user_id, comparison: dict) -> None:
    from workers.webhook_tasks import deliver_webhook

    for run in comparison.get("runs", []):
        if not run.get("regressions"):
            continue
        for webhook in webhooks_for_event(db, user_id, "eval.regression_detected"):
            payload = {
                "event": "eval.regression_detected",
                "eval_run_id": run["eval_run_id"],
                "baseline_run_id": comparison.get("baseline_run_id"),
                "regressions": run["regressions"],
                "delta_vs_baseline": run.get("delta_vs_baseline", {}),
            }
            deliver_webhook.delay(str(webhook.id), payload)
