import time

import redis.asyncio as aioredis

from src.gateway.domain.ports.rate_limit import RateLimitPort


class RateLimiter(RateLimitPort):
    """
    Implements rate limiting using a Redis sorted set sliding window.

    Each request is stored as a member with its timestamp as score.
    On each call: removes entries outside the window, adds current
    timestamp, counts remaining entries.

    All operations run in a single pipeline — atomic enough for the
    rate limiting use case (slight over-counting under extreme
    concurrency is acceptable and expected in sliding window implementations).

    Trades more memory per key vs fixed window INCR, but eliminates
    the burst problem at window boundaries.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds

        async with self._client.pipeline() as pipe:
            # Remove entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request with timestamp as score
            # Member needs to be unique — using timestamp + random suffix
            # avoids collisions under concurrent requests
            pipe.zadd(key, {f"{now}:{id(pipe)}": now})
            # Count entries within window
            pipe.zcard(key)
            # Reset expiration
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

        count = results[2]
        return count <= limit