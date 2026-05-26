from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

import redis.asyncio as aioredis

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort


class RedisLogWriter(LogPort):
    """
    Redis Streams adapter for dense gateway operational logs.

    These records are intentionally short-lived observability data, not a formal
    audit source of truth. Curated request audit events remain in PostgreSQL.
    """

    def __init__(
        self,
        client: aioredis.Redis,
        *,
        retention_days: int = 7,
        max_entries_per_tenant_per_day: int = 1000,
        redact_headers: Iterable[str] = (),
        stream_prefix: str = "sentra:tenant",
    ) -> None:
        self._client = client
        self._ttl_seconds = max(1, retention_days) * 24 * 60 * 60
        self._max_entries = max(1, max_entries_per_tenant_per_day)
        self._redact_headers = {h.lower() for h in redact_headers}
        self._stream_prefix = stream_prefix.strip(":")

    async def write(self, event: LogEvent) -> None:
        tenant_id = event.tenant_id or "unknown"
        day = event.timestamp.astimezone(timezone.utc).date().isoformat()
        stream_key = f"{self._stream_prefix}:{tenant_id}:gateway:raw_logs:{day}"
        record = self._serialize(event)

        await self._client.xadd(
            stream_key,
            {"event": json.dumps(record, ensure_ascii=False)},
            maxlen=self._max_entries,
            approximate=True,
        )
        await self._client.expire(stream_key, self._ttl_seconds)

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
