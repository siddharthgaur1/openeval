import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from litellm import completion, completion_cost
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.prompt import PromptTemplate
from models.user import User
from schemas.prompt import PlaygroundRequest, PlaygroundResult, PromptTemplateCreate, PromptTemplateOut
from services.eval_service import render_prompt_vars

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("", response_model=PromptTemplateOut, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    latest = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.user_id == current_user.id, PromptTemplate.name == payload.name)
        .order_by(PromptTemplate.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    prompt = PromptTemplate(
        user_id=current_user.id,
        name=payload.name,
        version=version,
        template=payload.template,
        variables=payload.variables,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("", response_model=list[PromptTemplateOut])
def list_prompts(name: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(PromptTemplate).filter(PromptTemplate.user_id == current_user.id)
    if name:
        query = query.filter(PromptTemplate.name == name)
    return query.order_by(PromptTemplate.name, PromptTemplate.version).all()


@router.get("/{name}/versions", response_model=list[PromptTemplateOut])
def get_prompt_versions(name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    versions = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.user_id == current_user.id, PromptTemplate.name == name)
        .order_by(PromptTemplate.version)
        .all()
    )
    if not versions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    return versions


@router.post("/{version_id}/promote", response_model=PromptTemplateOut)
def promote_version(version_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Atomic swap: this version becomes 'production', any other production
    version of the same prompt name is demoted to 'staging'.
    """
    target = db.query(PromptTemplate).filter(PromptTemplate.id == version_id, PromptTemplate.user_id == current_user.id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt version not found")

    current_production = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.user_id == current_user.id,
            PromptTemplate.name == target.name,
            PromptTemplate.status == "production",
            PromptTemplate.id != target.id,
        )
        .all()
    )
    for version in current_production:
        version.status = "staging"
    target.status = "production"
    db.commit()
    db.refresh(target)
    return target


@router.post("/{version_id}/playground", response_model=PlaygroundResult)
def run_playground(version_id: UUID, payload: PlaygroundRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    template = db.query(PromptTemplate).filter(PromptTemplate.id == version_id, PromptTemplate.user_id == current_user.id).first()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt version not found")

    rendered = render_prompt_vars(template.template, payload.variables)
    start = time.perf_counter()
    response = completion(model=payload.model, messages=[{"role": "user", "content": rendered}])
    latency_ms = (time.perf_counter() - start) * 1000
    output = response.choices[0].message.content or ""
    try:
        cost = completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    return PlaygroundResult(rendered_prompt=rendered, output=output, latency_ms=latency_ms, cost_usd=cost)
