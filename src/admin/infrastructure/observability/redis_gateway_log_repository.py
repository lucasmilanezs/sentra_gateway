from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.admin.domain.entities.raw_gateway_log import RawGatewayLog
from src.admin.domain.ports.raw_gateway_log_repository import RawGatewayLogRepositoryPort
from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error, safe_redis_url

logger = logging.getLogger(__name__)


class RedisGatewayLogRepository(RawGatewayLogRepositoryPort):
    """Reads short-lived gateway raw logs from Redis Streams.

    This adapter is an admin-side reader over operational Redis data. Redis log
    reads must never degrade the admin control plane when Redis is down.
    """

    def __init__(
        self,
        client: aioredis.Redis,
        *,
        stream_prefix: str = "sentra:tenant",
        redis_url: str | None = None,
        status_registry: DependencyStatusRegistry | None = None,
        status_name: str = "redis_raw_log_reader",
        redis_status_name: str = "redis",
        max_failures: int = 3,
        retry_cooldown_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._stream_prefix = stream_prefix.strip(":")
        self._redis_url = redis_url
        self._status_registry = status_registry
        self._status_name = status_name
        self._redis_status_name = redis_status_name
        self._max_failures = max(1, int(max_failures))
        self._retry_cooldown_seconds = max(1.0, float(retry_cooldown_seconds))
        self._local_failures = 0
        self._next_retry_at: float = 0.0

    async def list_recent(self, *, tenant_id: str | None, limit: int) -> list[RawGatewayLog]:
        if self._should_short_circuit():
            self._mark_short_circuited()
            return []

        try:
            keys = await self._keys_for_scope(tenant_id)
        except Exception as exc:
            await self._handle_failure(exc, phase="redis_scan_failed")
            return []

        logs: list[RawGatewayLog] = []
        per_key_limit = max(limit, 1)
        for key in keys:
            try:
                rows = await self._client.xrevrange(key, count=per_key_limit)
            except Exception as exc:
                await self._handle_failure(exc, phase="redis_stream_read_failed", stream_key=key)
                continue
            for entry_id, fields in rows:
                log = self._to_entity(entry_id, fields)
                if tenant_id and log.tenant_id != tenant_id:
                    continue
                logs.append(log)

        self._mark_ok()
        logs.sort(key=lambda item: item.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return logs[:limit]

    async def _keys_for_scope(self, tenant_id: str | None) -> list[str]:
        if tenant_id:
            pattern = f"{self._stream_prefix}:{tenant_id}:gateway:raw_logs:*"
        else:
            pattern = f"{self._stream_prefix}:*:gateway:raw_logs:*"
        keys: list[str] = []
        async for key in self._client.scan_iter(match=pattern, count=100):
            keys.append(key.decode("utf-8") if isinstance(key, bytes) else key)
        keys.sort(reverse=True)
        return keys

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
        if self._status_registry:
            self._status_registry.mark_degraded(
                self._status_name,
                "Leitura de logs operacionais ignorada temporariamente: Redis administrativo está em cooldown após falha recente.",
                reason_code="circuit_breaker_open",
                phase="cooldown",
                stream_prefix=self._stream_prefix,
            )

    def _mark_ok(self) -> None:
        self._local_failures = 0
        self._next_retry_at = 0.0
        if self._status_registry:
            self._status_registry.mark_ok(
                self._status_name,
                "Leitor de logs operacionais saudável: Redis aceitou a última consulta de streams.",
                reason_code="raw_log_read_ok",
                phase="operational",
                stream_prefix=self._stream_prefix,
            )
            self._status_registry.mark_ok(
                self._redis_status_name,
                "Redis administrativo respondeu durante leitura de logs operacionais.",
                reason_code="raw_log_read_ok",
                phase="operational",
                redis_url=safe_redis_url(self._redis_url) if self._redis_url else None,
            )

    async def _handle_failure(self, exc: Exception, *, phase: str, **metadata: Any) -> None:
        reason_code, human_reason = classify_connection_error(exc)
        self._local_failures += 1
        self._next_retry_at = datetime.now(timezone.utc).timestamp() + self._retry_cooldown_seconds

        if self._status_registry:
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
                detail=f"{human_reason}. A leitura de logs operacionais foi suspensa temporariamente; o Admin continua operacional.",
                reason_code=reason_code,
                human_reason=human_reason,
                phase=phase,
                retry_in_seconds=self._retry_cooldown_seconds,
                stream_prefix=self._stream_prefix,
                **metadata,
            )
            if self._local_failures >= self._max_failures or self._status_registry.get(self._status_name).attempts >= self._max_failures:
                self._status_registry.mark_inactive(
                    self._status_name,
                    "Leitor de logs operacionais inativo após falhas repetidas no Redis. A tela de logs pode ficar vazia até o Redis voltar.",
                    reason_code="retry_budget_exhausted",
                    phase="inactive",
                    stream_prefix=self._stream_prefix,
                )

        await self._disconnect_dirty_pool()
        logger.warning(
            "Falha ao ler logs operacionais do Redis [%s/%s]. Leitura degradada sem bloquear o Admin.",
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

    def _to_entity(self, entry_id: Any, fields: dict) -> RawGatewayLog:
        decoded_id = entry_id.decode("utf-8") if isinstance(entry_id, bytes) else str(entry_id)
        event_raw = self._field(fields, "event")
        try:
            payload = json.loads(event_raw) if event_raw else {}
        except json.JSONDecodeError:
            payload = {"raw": event_raw, "outcome": "MALFORMED_LOG_ENTRY"}
        timestamp = self._parse_datetime(payload.get("timestamp"))
        policy_checks = self._policy_checks(payload)
        header_checks = [c for c in policy_checks if "header" in str(c.get("check", ""))]
        param_checks = [c for c in policy_checks if "param" in str(c.get("check", ""))]
        layer_errors = payload.get("layer_errors") if isinstance(payload.get("layer_errors"), dict) else {}
        return RawGatewayLog(
            id=decoded_id,
            timestamp=timestamp,
            tenant_id=payload.get("tenant_id"),
            route_id=payload.get("route_id"),
            method=payload.get("method"),
            path=payload.get("path"),
            status_code=payload.get("status_code"),
            outcome=payload.get("outcome") or "UNKNOWN",
            latency_ms=payload.get("latency_ms"),
            summary=payload.get("summary") or self._summary(payload),
            payload={**payload, "redis_id": decoded_id},
            policy_summary=self._policy_summary(policy_checks),
            header_checks=header_checks,
            param_checks=param_checks,
            policy_checks=policy_checks,
            layer_errors=layer_errors,
        )

    def _field(self, fields: dict, name: str) -> str | None:
        value = fields.get(name) if name in fields else fields.get(name.encode("utf-8"))
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _policy_checks(self, payload: dict) -> list[dict]:
        raw = payload.get("policy_checks")
        return raw if isinstance(raw, list) else []

    def _policy_summary(self, checks: list[dict]) -> str:
        if not checks:
            return "Sem checks de política registrados"
        passed = sum(1 for check in checks if check.get("passed"))
        failed = len(checks) - passed
        return f"{passed} check(s) passaram, {failed} falharam"

    def _summary(self, payload: dict) -> str:
        method = payload.get("method") or "?"
        path = payload.get("path") or "?"
        status = payload.get("status_code") or "?"
        outcome = payload.get("outcome") or "UNKNOWN"
        return f"{method} {path} → {status} · {outcome}"
