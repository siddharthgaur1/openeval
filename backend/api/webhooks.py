from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.database import get_db
from models.user import User
from models.webhook import Webhook
from schemas.webhook import WebhookCreate, WebhookOut
from services.organization_service import get_default_project

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_id = payload.project_id or get_default_project(db, current_user).id
    check_project_role(db, current_user.id, project_id, "admin")  # webhooks can call out to arbitrary URLs - admin+ only

    webhook = Webhook(user_id=current_user.id, project_id=project_id, url=payload.url, events=payload.events, secret=payload.secret)
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("", response_model=list[WebhookOut])
def list_webhooks(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    return db.query(Webhook).filter(Webhook.project_id == project_id).all()


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    check_project_role(db, current_user.id, webhook.project_id, "admin")
    db.delete(webhook)
    db.commit()
