import logging
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api import api_router
from core.config import settings

logger = logging.getLogger("openeval")

if settings.jwt_secret == "change-me-in-prod":
    # Not a hard failure - a fresh `docker compose up` should still boot - but this
    # default key means anyone can forge a valid access token, so make it loud.
    logger.warning(
        "JWT_SECRET is unset and using the insecure default. Set a real secret "
        "before exposing this deployment beyond localhost (see infra/k8s/secret.example.yaml)."
    )

app = FastAPI(title="OpenEval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# openeval_api_request_duration_seconds{route} + friends, plus the custom counters
# in core/metrics.py, exposed at /metrics for infra/prometheus/prometheus.yml.
#
# When PROMETHEUS_MULTIPROC_DIR is set (see infra/docker-compose.yml), the Celery
# worker shares that directory and writes its own counters (eval_jobs_total) into
# it too - Instrumentator's default .expose() reads only the in-process registry,
# which would miss those, so /metrics is served manually via a multiprocess
# collector instead in that mode.
if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess

    Instrumentator().instrument(app)

    @app.get("/metrics")
    def metrics():
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
else:
    Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "ok"}
