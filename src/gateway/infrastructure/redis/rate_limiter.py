import time

import redis.asyncio as aioredis

from src.gateway.domain.ports.rate_limit import RateLimitPort


class RateLimiter(RateLimitPort):
    """Implements rate limiting using a Redis sorted set sliding window."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def is_allowed(
        self,
        *,
        tenant_id: str,
        route_id: str,
        client_ip: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        key = f"rate:{tenant_id}:{route_id}:{client_ip}"
        now = time.time()
        window_start = now - window_seconds

        async with self._client.pipeline() as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {f"{now}:{id(pipe)}": now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

        count = results[2]
        return count <= limit
