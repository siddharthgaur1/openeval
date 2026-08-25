from prometheus_client import Counter

# ponytail: single-process prometheus_client registry. traces_ingested_total /
# llm_cost_usd_total (incremented in the FastAPI process) show up at GET /metrics
# correctly; eval_jobs_total (incremented in the Celery worker process) does NOT,
# since it's a separate process with its own registry. Fix: set PROMETHEUS_MULTIPROC_DIR
# and use prometheus_client's multiprocess mode if worker-side metrics are needed.
traces_ingested_total = Counter("openeval_traces_ingested_total", "Total traces ingested")
eval_jobs_total = Counter("openeval_eval_jobs_total", "Total eval jobs by terminal status", ["status"])
llm_cost_usd_total = Counter("openeval_llm_cost_usd_total", "Total LLM cost in USD", ["provider", "model"])


def record_llm_cost(model: str, cost_usd: float) -> None:
    provider = model.split("/", 1)[0] if "/" in model else "unknown"
    llm_cost_usd_total.labels(provider=provider, model=model).inc(cost_usd)
