from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text

from src.shared.runtime.redis_diagnostics import classify_connection_error, parse_redis_endpoint, safe_redis_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _component(status: str, detail: str, **extra: Any) -> dict[str, Any]:
    payload = {"status": status, "detail": detail, "checked_at": _now()}
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


async def check_postgres(session_factory) -> dict[str, Any]:
    if not session_factory:
        return _component("not_configured", "Postgres session factory não está configurada")
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return _component("ok", "PostgreSQL administrativo respondeu ao SELECT 1")
    except Exception as exc:
        return _component("error", str(exc), error_type=type(exc).__name__)


async def check_redis(settings, client: aioredis.Redis | None) -> dict[str, Any]:
    if client is None:
        return _component("not_configured", "Redis client não está configurado")
    redis_url = getattr(settings, "redis_url", "redis://redis:6379/0")
    endpoint = parse_redis_endpoint(redis_url)
    try:
        await client.ping()
        return _component(
            "ok",
            "Redis administrativo respondeu ao PING",
            redis_url=safe_redis_url(redis_url),
            redis_host=endpoint.host,
            redis_port=endpoint.port,
        )
    except Exception as exc:
        reason_code, human_reason = classify_connection_error(exc)
        return _component(
            "error",
            human_reason,
            reason_code=reason_code,
            error_type=type(exc).__name__,
            last_error=str(exc),
            redis_url=safe_redis_url(redis_url),
            redis_host=endpoint.host,
            redis_port=endpoint.port,
        )


async def build_admin_health(admin) -> dict[str, Any]:
    settings = getattr(admin, "settings", None)
    postgres = await check_postgres(getattr(admin, "_session_factory", None))
    redis = await check_redis(settings, getattr(admin, "_redis_client", None))

    if postgres["status"] != "ok":
        status = "error"
        detail = "admin sem conexão saudável com PostgreSQL"
    elif redis["status"] != "ok":
        status = "degraded"
        detail = "admin operacional, mas Redis de notificações/logs está indisponível"
    else:
        status = "ok"
        detail = "admin saudável"

    return {
        "service": "admin",
        "status": status,
        "ready": postgres["status"] == "ok",
        "detail": detail,
        "checked_at": _now(),
        "checks": {
            "postgres": postgres,
            "redis": redis,
        },
        "postgres_connected": postgres.get("status") == "ok",
        "redis_connected": redis.get("status") == "ok",
    }
