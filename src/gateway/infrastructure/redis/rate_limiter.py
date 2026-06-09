from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis

from src.gateway.domain.ports.rate_limit import RateLimitPort
from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error

logger = logging.getLogger(__name__)


class RateLimiter(RateLimitPort):
    """Implements rate limiting using a Redis sorted set sliding window."""

    def __init__(
        self,
        client: aioredis.Redis,
        *,
        fail_open: bool = True,
        status_registry: DependencyStatusRegistry | None = None,
        status_name: str = "redis_rate_limit",
        max_failures: int | None = None,
        retry_cooldown_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._fail_open = fail_open
        self._status_registry = status_registry
        self._status_name = status_name
        self._max_failures = max(1, int(max_failures or 5))
        self._retry_cooldown_seconds = max(1.0, float(retry_cooldown_seconds))

    async def is_allowed(
        self,
        *,
        tenant_id: str,
        route_id: str,
        client_ip: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        if self._should_short_circuit():
            return self._fail_open_result()

        key = f"rate:{tenant_id}:{route_id}:{client_ip}"
        now = time.time()
        window_start = now - window_seconds

        try:
            async with self._client.pipeline() as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {f"{now}:{id(pipe)}": now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds)
                results = await pipe.execute()

            if self._status_registry:
                self._status_registry.mark_ok(
                    self._status_name,
                    "Rate limit operacional: Redis aceitou a escrita do contador desta requisição.",
                    reason_code="rate_limit_write_ok",
                    phase="operational",
                    fail_open=self._fail_open,
                    key_prefix="rate",
                )

            count = results[2]
            return count <= limit
        except Exception as exc:
            reason_code, human_reason = classify_connection_error(exc)
            if self._status_registry:
                detail = (
                    f"{human_reason}. A limitação de requisições foi liberada em fail-open para não interromper o proxy."
                    if self._fail_open
                    else f"{human_reason}. A limitação de requisições não pôde ser aplicada."
                )
                self._status_registry.mark_error(
                    self._status_name,
                    exc,
                    detail=detail,
                    reason_code=reason_code,
                    human_reason=human_reason,
                    phase="redis_write_failed",
                    retry_in_seconds=self._retry_cooldown_seconds,
                    fail_open=self._fail_open,
                    key_prefix="rate",
                )
                if self._status_registry.get(self._status_name).attempts >= self._max_failures:
                    self._status_registry.mark_inactive(
                        self._status_name,
                        "Rate limit inativo após falhas repetidas no Redis. O gateway continua operando em fail-open sem tocar no Redis no caminho crítico.",
                        reason_code="retry_budget_exhausted",
                        phase="inactive",
                        fail_open=self._fail_open,
                        key_prefix="rate",
                    )
            if self._fail_open:
                logger.warning(
                    "Redis rate limiter unavailable [%s/%s]; allowing request by fail-open policy.",
                    reason_code,
                    type(exc).__name__,
                )
                return True
            raise

    def _should_short_circuit(self) -> bool:
        if self._status_registry is None:
            return False
        now = datetime.now(timezone.utc)

        # The shared Redis connectivity flag is updated by /health. If Redis is
        # already known to be down, do not let the critical request path pay a DNS
        # resolution/socket timeout just to rediscover the same outage.
        redis_state = self._status_registry.get("redis_ping")
        if redis_state.status in {"error", "inactive"}:
            return True

        state = self._status_registry.get(self._status_name)
        if state.status == "inactive":
            return True
        if state.next_retry_at is not None and state.next_retry_at > now:
            return True
        return False

    def _fail_open_result(self) -> bool:
        if self._fail_open:
            return True
        raise RuntimeError("Rate limit Redis dependency is unavailable and fail-open is disabled.")
