from fastapi import APIRouter

from api.analytics import router as analytics_router
from api.annotations import router as annotations_router
from api.auth import router as auth_router
from api.datasets import router as datasets_router
from api.evals import router as evals_router
from api.experiments import router as experiments_router
from api.organizations import router as organizations_router
from api.otlp import router as otlp_router
from api.prompts import router as prompts_router
from api.traces import router as traces_router
from api.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(traces_router)
api_router.include_router(otlp_router)
api_router.include_router(datasets_router)
api_router.include_router(prompts_router)
api_router.include_router(evals_router)
api_router.include_router(experiments_router)
api_router.include_router(webhooks_router)
api_router.include_router(analytics_router)
api_router.include_router(organizations_router)
api_router.include_router(annotations_router)
