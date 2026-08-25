import redis

from core.config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def progress_channel(eval_run_id: str) -> str:
    return f"eval-progress:{eval_run_id}"


def publish_progress(eval_run_id: str, payload: dict) -> None:
    import json

    redis_client.publish(progress_channel(eval_run_id), json.dumps(payload))
