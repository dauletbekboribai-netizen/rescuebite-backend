import time
from fastapi import HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings

settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def rate_limit(request: Request, prefix: str, limit: int = 5, window_seconds: int = 60) -> None:
    ip = request.client.host if request.client else 'unknown'
    key = f'rl:{prefix}:{ip}:{int(time.time() // window_seconds)}'
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window_seconds)
        if count > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='rate limit exceeded')
    except RedisError:
        return
