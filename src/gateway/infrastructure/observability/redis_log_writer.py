from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

import redis.asyncio as aioredis

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort
from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error

logger = logging.getLogger(__name__)


class RedisLogWriter(LogPort):
    """
    Redis Streams adapter for dense gateway operational logs.

    These records are short-lived observability data, not formal audit data.
    If Redis becomes unavailable, this adapter marks the component as degraded
    and lets the caller decide how to handle the failed write.
    """

    def __init__(
        self,
        client: aioredis.Redis,
        *,
        retention_days: int = 7,
        max_entries_per_tenant_per_day: int = 1000,
        redact_headers: Iterable[str] = (),
        stream_prefix: str = "sentra:tenant",
        status_registry: DependencyStatusRegistry | None = None,
        status_name: str = "redis_raw_logs",
        max_failures: int | None = None,
        retry_cooldown_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._ttl_seconds = max(1, retention_days) * 24 * 60 * 60
        self._max_entries = max(1, max_entries_per_tenant_per_day)
        self._redact_headers = {h.lower() for h in redact_headers}
        self._stream_prefix = stream_prefix.strip(":")
        self._status_registry = status_registry
        self._status_name = status_name
        self._max_failures = max(1, int(max_failures or 5))
        self._retry_cooldown_seconds = max(1.0, float(retry_cooldown_seconds))

    async def write(self, event: LogEvent) -> None:
        if self._should_short_circuit():
            return

        tenant_id = event.tenant_id or "unknown"
        day = event.timestamp.astimezone(timezone.utc).date().isoformat()
        stream_key = f"{self._stream_prefix}:{tenant_id}:gateway:raw_logs:{day}"
        record = self._serialize(event)

        try:
            await self._client.xadd(
                stream_key,
                {"event": json.dumps(record, ensure_ascii=False)},
                maxlen=self._max_entries,
                approximate=True,
            )
            await self._client.expire(stream_key, self._ttl_seconds)
            if self._status_registry:
                self._status_registry.mark_ok(
                    self._status_name,
                    "Logs operacionais saudáveis: último evento bruto gravado no Redis com sucesso.",
                    reason_code="raw_log_write_ok",
                    phase="operational",
                    stream_key=stream_key,
                )
        except Exception as exc:
            reason_code, human_reason = classify_connection_error(exc)
            if self._status_registry:
                self._status_registry.mark_error(
                    self._status_name,
                    exc,
                    detail=f"{human_reason}. A escrita de logs operacionais foi interrompida; auditoria persistente não é afetada.",
                    reason_code=reason_code,
                    human_reason=human_reason,
                    phase="redis_stream_write_failed",
                    retry_in_seconds=self._retry_cooldown_seconds,
                    stream_key=stream_key,
                )
                if self._status_registry.get(self._status_name).attempts >= self._max_failures:
                    self._status_registry.mark_inactive(
                        self._status_name,
                        "Logs operacionais em Redis inativos após falhas repetidas de escrita. O gateway continua encaminhando requisições sem tocar no Redis para logs no caminho crítico.",
                        reason_code="retry_budget_exhausted",
                        phase="inactive",
                        stream_key=stream_key,
                    )
            logger.warning(
                "Failed to write gateway raw log to Redis [%s/%s]; operational logging is degraded.",
                reason_code,
                type(exc).__name__,
            )
            return

    def _should_short_circuit(self) -> bool:
        if self._status_registry is None:
            return False
        now = datetime.now(timezone.utc)

        # The shared Redis connectivity flag is updated by /health. If Redis is
        # already known to be down, raw operational logging must not add latency to
        # the proxy path by attempting a Redis write on every request.
        redis_state = self._status_registry.get("redis_ping")
        if redis_state.status in {"error", "inactive"}:
            return True

        state = self._status_registry.get(self._status_name)
        if state.status == "inactive":
            return True
        if state.next_retry_at is not None and state.next_retry_at > now:
            return True
        return False

    def _serialize(self, event: LogEvent) -> dict:
        return {
            "timestamp": event.timestamp.isoformat(),
            "method": event.method,
            "path": event.path,
            "upstream_url": event.upstream_url,
            "status_code": event.status_code,
            "latency_ms": round(event.latency_ms, 2),
            "route_id": event.route_id,
            "tenant_id": event.tenant_id,
            "client_ip": event.client_ip,
            "error": event.error,
            "outcome": event.outcome,
            "request_headers": self._redact_mapping(event.request_headers),
            "query_params": dict(event.query_params),
            "policy_checks": event.policy_checks,
            "upstream_response_headers": self._redact_mapping(event.upstream_response_headers),
            "upstream_response_body_preview": event.upstream_response_body_preview,
            "layer_errors": event.layer_errors,
            "summary": self._summary(event),
        }

    def _redact_mapping(self, values: dict[str, str]) -> dict[str, str]:
        clean: dict[str, str] = {}
        for key, value in values.items():
            clean[key] = "[REDACTED]" if key.lower() in self._redact_headers else value
        return clean

    def _summary(self, event: LogEvent) -> str:
        route = (event.route_id or "no-route")[:8]
        return f"{event.method} {event.path} → {event.status_code} · {event.outcome} · {route}"
