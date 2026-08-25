import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from litellm import completion, completion_cost
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.rbac import check_project_role
from core.database import get_db
from models.prompt import PromptTemplate
from models.user import User
from schemas.prompt import PlaygroundRequest, PlaygroundResult, PromptTemplateCreate, PromptTemplateOut
from services.eval_service import render_prompt_vars
from services.organization_service import get_default_project

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("", response_model=PromptTemplateOut, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project_id = payload.project_id or get_default_project(db, current_user).id
    check_project_role(db, current_user.id, project_id, "member")

    latest = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.project_id == project_id, PromptTemplate.name == payload.name)
        .order_by(PromptTemplate.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    prompt = PromptTemplate(
        user_id=current_user.id,
        project_id=project_id,
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
def list_prompts(project_id: UUID, name: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    query = db.query(PromptTemplate).filter(PromptTemplate.project_id == project_id)
    if name:
        query = query.filter(PromptTemplate.name == name)
    return query.order_by(PromptTemplate.name, PromptTemplate.version).all()


@router.get("/{name}/versions", response_model=list[PromptTemplateOut])
def get_prompt_versions(name: str, project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_project_role(db, current_user.id, project_id, "viewer")
    versions = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.project_id == project_id, PromptTemplate.name == name)
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
    target = db.query(PromptTemplate).filter(PromptTemplate.id == version_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt version not found")
    check_project_role(db, current_user.id, target.project_id, "member")

    current_production = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.project_id == target.project_id,
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
    template = db.query(PromptTemplate).filter(PromptTemplate.id == version_id).first()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt version not found")
    check_project_role(db, current_user.id, template.project_id, "member")

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
