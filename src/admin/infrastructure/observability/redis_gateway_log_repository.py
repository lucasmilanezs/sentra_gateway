from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.admin.domain.entities.raw_gateway_log import RawGatewayLog
from src.admin.domain.ports.raw_gateway_log_repository import RawGatewayLogRepositoryPort


class RedisGatewayLogRepository(RawGatewayLogRepositoryPort):
    """Reads short-lived gateway raw logs from Redis Streams."""

    def __init__(self, client: aioredis.Redis, *, stream_prefix: str = "sentra:tenant") -> None:
        self._client = client
        self._stream_prefix = stream_prefix.strip(":")

    async def list_recent(self, *, tenant_id: str | None, limit: int) -> list[RawGatewayLog]:
        keys = await self._keys_for_scope(tenant_id)
        logs: list[RawGatewayLog] = []
        per_key_limit = max(limit, 1)
        for key in keys:
            try:
                rows = await self._client.xrevrange(key, count=per_key_limit)
            except Exception:
                continue
            for entry_id, fields in rows:
                log = self._to_entity(entry_id, fields)
                if tenant_id and log.tenant_id != tenant_id:
                    continue
                logs.append(log)
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

    def _to_entity(self, entry_id: Any, fields: dict) -> RawGatewayLog:
        decoded_id = entry_id.decode("utf-8") if isinstance(entry_id, bytes) else str(entry_id)
        event_raw = self._field(fields, "event")
        try:
            payload = json.loads(event_raw) if event_raw else {}
        except json.JSONDecodeError:
            payload = {"raw": event_raw, "outcome": "MALFORMED_LOG_ENTRY"}
        timestamp = self._parse_datetime(payload.get("timestamp"))
        summary = payload.get("summary") or self._summary(payload)
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
            summary=summary,
            payload={**payload, "redis_id": decoded_id},
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

    def _summary(self, payload: dict) -> str:
        method = payload.get("method") or "?"
        path = payload.get("path") or "?"
        status = payload.get("status_code") or "?"
        outcome = payload.get("outcome") or "UNKNOWN"
        route = str(payload.get("route_id") or "no-route")[:8]
        return f"{method} {path} → {status} · {outcome} · {route}"
