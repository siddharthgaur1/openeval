import os

from celery import Celery
from celery.signals import worker_process_shutdown

from core.config import settings

celery_app = Celery("openeval", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"workers.tasks.*": {"queue": "evals"}}
celery_app.autodiscover_tasks(["workers"])


@worker_process_shutdown.connect
def _mark_prometheus_process_dead(pid, **kwargs):
    """Required for correct Prometheus multiprocess mode with Celery's prefork pool:
    without this, a dead worker subprocess's mmap'd metric file is left behind and
    double-counted (or stale) the next time a subprocess reuses that PID.
    """
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(pid)
