"""Redis sliding-window rate limiter, keyed per API key / user id."""

import time

from core.redis import redis_client


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Returns (allowed, remaining). Uses a Redis sorted set as a sliding window:
    each request is a member scored by its timestamp; members older than the
    window are trimmed before counting.
    """
    now = time.time()
    window_start = now - window_seconds
    redis_key = f"ratelimit:{key}"

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(redis_key, 0, window_start)
    pipe.zcard(redis_key)
    pipe.zadd(redis_key, {str(now): now})
    pipe.expire(redis_key, window_seconds)
    _, count, _, _ = pipe.execute()

    if count >= limit:
        redis_client.zrem(redis_key, str(now))
        return False, 0
    return True, limit - count - 1
