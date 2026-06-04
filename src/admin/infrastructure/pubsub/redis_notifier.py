from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error, safe_redis_url

logger = logging.getLogger(__name__)

CHANNEL = "sentra:config:updated"


class RedisConfigNotifier(ConfigNotifier):
    """Redis pub/sub adapter for gateway configuration update notifications.

    Redis is a delivery mechanism for dynamic reload notifications, not the source
    of truth for configuration. When Redis is unavailable, admin writes must keep
    succeeding and the notifier must avoid repeatedly touching Redis on every
    configuration change.
    """

    def __init__(
        self,
        client: aioredis.Redis,
        *,
        redis_url: str | None = None,
        status_registry: DependencyStatusRegistry | None = None,
        status_name: str = "redis_notifier",
        redis_status_name: str = "redis",
        max_failures: int = 3,
        retry_cooldown_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._redis_url = redis_url
        self._status_registry = status_registry
        self._status_name = status_name
        self._redis_status_name = redis_status_name
        self._max_failures = max(1, int(max_failures))
        self._retry_cooldown_seconds = max(1.0, float(retry_cooldown_seconds))
        self._local_failures = 0
        self._next_retry_at: float = 0.0

    async def notify_config_updated(self) -> None:
        if self._should_short_circuit():
            self._mark_short_circuited()
            return

        try:
            await self._client.publish(CHANNEL, "updated")
            self._local_failures = 0
            self._next_retry_at = 0.0
            if self._status_registry:
                self._status_registry.mark_ok(
                    self._status_name,
                    "Notificador Redis saudável: última alteração administrativa foi publicada no canal de configuração.",
                    reason_code="redis_publish_ok",
                    phase="operational",
                    channel=CHANNEL,
                )
                self._status_registry.mark_ok(
                    self._redis_status_name,
                    "Redis administrativo respondeu durante publicação de notificação.",
                    reason_code="redis_publish_ok",
                    phase="operational",
                    redis_url=safe_redis_url(self._redis_url) if self._redis_url else None,
                )
            logger.info("Notificação de atualização de configuração publicada.")
        except Exception as exc:
            await self._handle_failure(exc)

    def _should_short_circuit(self) -> bool:
        now = datetime.now(timezone.utc).timestamp()

        if self._status_registry:
            redis_status = self._status_registry.status_of(self._redis_status_name)
            own_status = self._status_registry.status_of(self._status_name)
            if redis_status == "inactive" or own_status == "inactive":
                return True
            if redis_status == "error" and now < self._next_retry_at:
                return True

        return now < self._next_retry_at

    def _mark_short_circuited(self) -> None:
        if not self._status_registry:
            return
        self._status_registry.mark_degraded(
            self._status_name,
            "Notificação Redis ignorada temporariamente: Redis administrativo está em cooldown após falha recente. A configuração foi salva no PostgreSQL; o gateway pode precisar de novo reload quando o Redis voltar.",
            reason_code="circuit_breaker_open",
            phase="cooldown",
            channel=CHANNEL,
        )

    async def _handle_failure(self, exc: Exception) -> None:
        reason_code, human_reason = classify_connection_error(exc)
        self._local_failures += 1
        self._next_retry_at = datetime.now(timezone.utc).timestamp() + self._retry_cooldown_seconds

        if self._status_registry:
            detail = (
                f"{human_reason}. A alteração administrativa foi persistida, mas o aviso de reload ao gateway não pôde ser publicado."
            )
            self._status_registry.mark_error(
                self._redis_status_name,
                exc,
                detail=human_reason,
                reason_code=reason_code,
                human_reason=human_reason,
                phase="admin_redis_unavailable",
                retry_in_seconds=self._retry_cooldown_seconds,
                redis_url=safe_redis_url(self._redis_url) if self._redis_url else None,
            )
            self._status_registry.mark_error(
                self._status_name,
                exc,
                detail=detail,
                reason_code=reason_code,
                human_reason=human_reason,
                phase="redis_publish_failed",
                retry_in_seconds=self._retry_cooldown_seconds,
                channel=CHANNEL,
            )
            if self._local_failures >= self._max_failures or self._status_registry.get(self._status_name).attempts >= self._max_failures:
                self._status_registry.mark_inactive(
                    self._status_name,
                    "Notificador Redis inativo após falhas repetidas. O Admin continuará salvando configurações; a mensageria será reabilitada quando o healthcheck detectar Redis novamente.",
                    reason_code="retry_budget_exhausted",
                    phase="inactive",
                    channel=CHANNEL,
                )

        await self._disconnect_dirty_pool()

        # Best-effort: notification failures must not rollback admin writes.
        logger.warning(
            "Falha ao publicar notificação Redis [%s/%s]. Circuit breaker aplicado; alteração administrativa permanece persistida.",
            reason_code,
            type(exc).__name__,
        )

    async def _disconnect_dirty_pool(self) -> None:
        try:
            await self._client.connection_pool.disconnect(inuse_connections=True)
        except TypeError:
            try:
                await self._client.connection_pool.disconnect()
            except Exception:
                pass
        except Exception:
            pass
