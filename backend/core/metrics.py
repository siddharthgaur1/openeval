from prometheus_client import Counter

# When PROMETHEUS_MULTIPROC_DIR is set, prometheus_client transparently switches
# these Counters to write into per-process mmap files in that directory instead of
# an in-memory registry - this is what lets the FastAPI process's /metrics endpoint
# (see main.py) also report counters incremented by the separate Celery worker
# process, as long as both processes share that directory (see infra/docker-compose.yml).
traces_ingested_total = Counter("openeval_traces_ingested_total", "Total traces ingested")
eval_jobs_total = Counter("openeval_eval_jobs_total", "Total eval jobs by terminal status", ["status"])
llm_cost_usd_total = Counter("openeval_llm_cost_usd_total", "Total LLM cost in USD", ["provider", "model"])


def record_llm_cost(model: str, cost_usd: float) -> None:
    provider = model.split("/", 1)[0] if "/" in model else "unknown"
    llm_cost_usd_total.labels(provider=provider, model=model).inc(cost_usd)
