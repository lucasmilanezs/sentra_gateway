from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error, parse_redis_endpoint, safe_redis_url

router = APIRouter(tags=["health"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_status(registry: DependencyStatusRegistry | None, name: str, detail: str) -> dict[str, Any]:
    if registry is None:
        return {"status": "unknown", "detail": detail}
    data = registry.as_dict().get(name)
    if not data:
        return {"status": "unknown", "detail": detail}
    return data


def _snapshot_check(request: Request) -> dict[str, Any]:
    snapshot = getattr(request.app.state, "snapshot", None)
    if not snapshot:
        return {"status": "not_loaded", "detail": "snapshot de configuração não foi inicializada"}

    loaded_at = getattr(snapshot, "loaded_at", None)
    age = round((datetime.now(timezone.utc) - loaded_at).total_seconds(), 1) if loaded_at else None
    status = "ok" if loaded_at else "not_loaded"
    return {
        "status": status,
        "detail": "última snapshot carregada com sucesso" if loaded_at else "snapshot ainda não carregada",
        "routes_loaded": snapshot.route_count(),
        "tenants_loaded": snapshot.tenant_count(),
        "policies_loaded": snapshot.policy_count(),
        "loaded_at": loaded_at.isoformat() if loaded_at else None,
        "last_successful_load_at": loaded_at.isoformat() if loaded_at else None,
        "age_seconds": age,
    }


async def _postgres_ping(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "PostgreSQL respondeu ao SELECT 1"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc), "error_type": type(exc).__name__}
    finally:
        await engine.dispose()


async def _redis_ping(redis_url: str, *, connect_timeout_seconds: float, operation_timeout_seconds: float) -> dict[str, Any]:
    endpoint = parse_redis_endpoint(redis_url)
    client = aioredis.from_url(
        redis_url,
        socket_connect_timeout=connect_timeout_seconds,
        socket_timeout=operation_timeout_seconds,
        health_check_interval=None,
        retry_on_timeout=False,
    )
    try:
        await asyncio.wait_for(client.ping(), timeout=connect_timeout_seconds + operation_timeout_seconds + 0.2)
        return {
            "status": "ok",
            "detail": "Redis respondeu ao PING",
            "redis_url": safe_redis_url(redis_url),
            "redis_host": endpoint.host,
            "redis_port": endpoint.port,
        }
    except Exception as exc:
        reason_code, human_reason = classify_connection_error(exc)
        return {
            "status": "error",
            "detail": human_reason,
            "reason_code": reason_code,
            "error_type": type(exc).__name__,
            "last_error": str(exc),
            "redis_url": safe_redis_url(redis_url),
            "redis_host": endpoint.host,
            "redis_port": endpoint.port,
        }
    finally:
        await client.aclose()


async def _build_health(request: Request) -> dict[str, Any]:
    settings = getattr(request.app.state, "settings", None)
    registry: DependencyStatusRegistry | None = getattr(request.app.state, "dependency_status", None)

    checks: dict[str, Any] = {"snapshot": _snapshot_check(request)}
    if settings is None:
        checks["postgres"] = {"status": "not_configured", "detail": "settings não configurado"}
        checks["redis"] = {"status": "not_configured", "detail": "settings não configurado"}
    else:
        postgres, redis = await asyncio.gather(
            _postgres_ping(settings.database_url),
            _redis_ping(
                settings.redis_url,
                connect_timeout_seconds=float(getattr(settings, "redis_connect_timeout_seconds", 1.0)),
                operation_timeout_seconds=float(getattr(settings, "redis_operation_timeout_seconds", 1.5)),
            ),
        )
        checks["postgres"] = postgres
        checks["redis"] = redis

    checks["redis_pubsub"] = _runtime_status(registry, "redis_pubsub", "mensageria ainda não estabeleceu estado conhecido")
    checks["redis_rate_limit"] = _runtime_status(registry, "redis_rate_limit", "rate limit ainda não foi exercitado neste runtime")
    checks["redis_raw_logs"] = _runtime_status(registry, "redis_raw_logs", "logs operacionais ainda não foram escritos neste runtime")
    checks["postgres_audit"] = _runtime_status(registry, "postgres_audit", "auditoria PostgreSQL ainda não registrou estado conhecido")
    checks["snapshot_reload"] = _runtime_status(registry, "snapshot_reload", "nenhum reload de snapshot falhou neste runtime")

    critical_ok = checks["snapshot"].get("status") == "ok" and checks["postgres"].get("status") == "ok"
    if not critical_ok:
        status = "error"
        detail = "gateway sem dependências críticas suficientes: snapshot ou PostgreSQL indisponível"
    elif checks["redis"].get("status") != "ok":
        status = "degraded"
        detail = "gateway operacional com snapshot local; Redis indisponível afeta Pub/Sub, rate limit e logs operacionais"
    elif any(checks[name].get("status") in {"error", "inactive"} for name in ("redis_pubsub", "redis_rate_limit", "redis_raw_logs")):
        status = "degraded"
        detail = "gateway operacional, mas algum componente Redis de runtime está degradado"
    else:
        status = "ok"
        detail = "gateway saudável"

    return {
        "service": "gateway",
        "status": status,
        "ready": critical_ok,
        "detail": detail,
        "checked_at": _now(),
        "checks": checks,
    }


@router.get("/health/live")
@router.get("/api/v1/health/live", include_in_schema=False)
async def health_live() -> dict[str, Any]:
    return {"service": "gateway", "status": "ok", "detail": "processo HTTP do gateway está vivo", "checked_at": _now()}


@router.get("/health/ready")
@router.get("/api/v1/health/ready", include_in_schema=False)
async def health_ready(request: Request) -> dict[str, Any]:
    return await _build_health(request)


@router.get("/health/dependencies")
@router.get("/api/v1/health/dependencies", include_in_schema=False)
async def health_dependencies(request: Request) -> dict[str, Any]:
    return await _build_health(request)


@router.get("/health")
@router.get("/api/v1/health", include_in_schema=False)
async def health(request: Request) -> dict[str, Any]:
    return await _build_health(request)
