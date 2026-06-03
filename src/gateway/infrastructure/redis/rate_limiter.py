from __future__ import annotations

import logging
import time

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
    ) -> None:
        self._client = client
        self._fail_open = fail_open
        self._status_registry = status_registry
        self._status_name = status_name
        self._max_failures = max_failures if max_failures and max_failures > 0 else None

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
                    "rate limit aplicado com Redis",
                    fail_open=self._fail_open,
                    key_prefix="rate",
                )

            count = results[2]
            return count <= limit
        except Exception as exc:
            reason_code, human_reason = classify_connection_error(exc)
            if self._status_registry:
                current_attempts = self._status_registry.get(self._status_name).attempts + 1
                if self._max_failures is not None and current_attempts >= self._max_failures:
                    self._status_registry.mark_inactive(
                        self._status_name,
                        (
                            f"{human_reason}; rate limit desativado temporariamente após "
                            f"{current_attempts} falha(s). Requests seguem em fail-open."
                            if self._fail_open
                            else f"{human_reason}; rate limit indisponível após {current_attempts} falha(s)."
                        ),
                        reason_code="runtime_failure_budget_exhausted",
                        human_reason=human_reason,
                        fail_open=self._fail_open,
                        key_prefix="rate",
                        max_failures=self._max_failures,
                    )
                else:
                    self._status_registry.mark_error(
                        self._status_name,
                        exc,
                        detail=(
                            f"{human_reason}; rate limit operando em fail-open"
                            if self._fail_open else human_reason
                        ),
                        reason_code=reason_code,
                        human_reason=human_reason,
                        fail_open=self._fail_open,
                        key_prefix="rate",
                        max_failures=self._max_failures,
                    )
            if self._fail_open:
                logger.warning(
                    "Redis rate limiter unavailable [%s/%s]; allowing request by fail-open policy.",
                    reason_code,
                    type(exc).__name__,
                )
                return True
            raise
