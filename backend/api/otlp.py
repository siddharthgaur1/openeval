"""Minimal OTLP/HTTP JSON trace ingestion. Accepts the standard OTLP JSON export
shape (resourceSpans -> scopeSpans -> spans) and maps span attributes named
`llm.*` onto our Trace model. This is intentionally a subset of the OTel spec:
full protobuf/gRPC OTLP is out of scope for the MVP.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from models.trace import Trace
from models.user import User

router = APIRouter(prefix="/v1/traces", tags=["otlp"])


def _attr_dict(attributes: list[dict]) -> dict:
    out = {}
    for attr in attributes or []:
        key = attr.get("key")
        value = attr.get("value", {})
        out[key] = next(iter(value.values()), None) if value else None
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
async def ingest_otlp(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    created = 0
    for resource_span in body.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                attrs = _attr_dict(span.get("attributes", []))
                start = int(span.get("startTimeUnixNano", 0))
                end = int(span.get("endTimeUnixNano", 0))
                latency_ms = max(0.0, (end - start) / 1_000_000) if start and end else 0.0
                trace = Trace(
                    user_id=current_user.id,
                    name=span.get("name", "llm-call"),
                    model=attrs.get("llm.model", "unknown"),
                    prompt=str(attrs.get("llm.prompt", "")),
                    response=str(attrs.get("llm.response", "")),
                    latency_ms=latency_ms,
                    prompt_tokens=int(attrs.get("llm.prompt_tokens", 0) or 0),
                    completion_tokens=int(attrs.get("llm.completion_tokens", 0) or 0),
                    cost_usd=float(attrs.get("llm.cost_usd", 0) or 0),
                    tags={k: v for k, v in attrs.items() if k.startswith("tag.")},
                )
                db.add(trace)
                created += 1
    db.commit()
    return {"accepted": created}
