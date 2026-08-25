from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api import api_router

app = FastAPI(title="OpenEval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# openeval_api_request_duration_seconds{route} + friends, plus the custom
# counters in core/metrics.py, all exposed at /metrics for infra/prometheus/prometheus.yml.
Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "ok"}
