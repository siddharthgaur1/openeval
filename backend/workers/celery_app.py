from celery import Celery

from core.config import settings

celery_app = Celery("openeval", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"workers.tasks.*": {"queue": "evals"}}
celery_app.autodiscover_tasks(["workers"])
