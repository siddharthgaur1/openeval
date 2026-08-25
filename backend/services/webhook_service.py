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


def webhooks_for_event(db: Session, project_id, event: str) -> list[Webhook]:
    hooks = db.query(Webhook).filter(Webhook.project_id == project_id, Webhook.is_active.is_(True)).all()
    return [h for h in hooks if event in h.events]


def build_payload(event: str, eval_run) -> dict:
    return {
        "event": event,
        "eval_run_id": str(eval_run.id),
        "status": eval_run.status,
        "summary": eval_run.summary,
    }


def dispatch_regression_webhooks(db: Session, comparison: dict, run_project_map: dict) -> None:
    """Fire eval.regression_detected only to webhooks registered on the *regressed
    run's own* project - `run_project_map` maps str(eval_run_id) -> project_id, so a
    compare spanning multiple projects never leaks one project's regression to
    another project's webhook.
    """
    from workers.webhook_tasks import deliver_webhook

    for run in comparison.get("runs", []):
        if not run.get("regressions"):
            continue
        project_id = run_project_map.get(run["eval_run_id"])
        if project_id is None:
            continue
        for webhook in webhooks_for_event(db, project_id, "eval.regression_detected"):
            payload = {
                "event": "eval.regression_detected",
                "eval_run_id": run["eval_run_id"],
                "baseline_run_id": comparison.get("baseline_run_id"),
                "regressions": run["regressions"],
                "delta_vs_baseline": run.get("delta_vs_baseline", {}),
            }
            deliver_webhook.delay(str(webhook.id), payload)
