import json

import httpx

from core.database import SessionLocal
from models.webhook import Webhook
from services.webhook_service import sign_payload
from workers.celery_app import celery_app


@celery_app.task(name="workers.webhook_tasks.deliver_webhook", bind=True, max_retries=3, default_retry_delay=30)
def deliver_webhook(self, webhook_id: str, payload: dict):
    db = SessionLocal()
    try:
        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook or not webhook.is_active:
            return

        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            headers["X-OpenEval-Signature"] = sign_payload(webhook.secret, body)

        try:
            httpx.post(webhook.url, content=body, headers=headers, timeout=10.0).raise_for_status()
        except httpx.HTTPError as exc:
            raise self.retry(exc=exc)
    finally:
        db.close()
