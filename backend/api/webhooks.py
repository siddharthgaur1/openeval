from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.user import User
from models.webhook import Webhook
from schemas.webhook import WebhookCreate, WebhookOut

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = Webhook(user_id=current_user.id, url=payload.url, events=payload.events, secret=payload.secret)
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Webhook).filter(Webhook.user_id == current_user.id).all()


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id, Webhook.user_id == current_user.id).first()
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    db.delete(webhook)
    db.commit()
