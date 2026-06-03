from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error, parse_redis_endpoint, safe_redis_url

router = APIRouter(tags=["health"])

PUBLIC_CHECKS = {"snapshot", "postgres", "redis_ping"}
SENSITIVE_CHECKS = {"redis_pubsub", "redis_rate_limit", "redis_raw_logs", "postgres_audit", "snapshot_reload"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_superuser_request(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    auth = request.headers.get("authorization") or ""
    if not settings or not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.admin_jwt_secret, algorithms=[settings.admin_jwt_algorithm])
    except JWTError:
        return False
    return payload.get("role") == "superuser"


def _snapshot_check(request: Request) -> dict[str, Any]:
    snapshot = getattr(request.app.state, "snapshot", None)
    if not snapshot:
        return {
            "status": "not_loaded",
            "detail": "Snapshot de configuração não foi inicializada.",
            "human_detail": "Snapshot de configuração não foi inicializada.",
        }
    loaded_at = getattr(snapshot, "loaded_at", None)
    age = round((datetime.now(timezone.utc) - loaded_at).total_seconds(), 1) if loaded_at else None
    status = "ok" if loaded_at else "not_loaded"
    return {
        "status": status,
        "detail": "Última snapshot carregada com sucesso." if loaded_at else "Snapshot ainda não carregada.",
        "routes_loaded": snapshot.route_count(),
        "tenants_loaded": snapshot.tenant_count(),
        "policies_loaded": snapshot.policy_count(),
        "loaded_at": loaded_at.isoformat() if loaded_at else None,
        "last_successful_load_at": loaded_at.isoformat() if loaded_at else None,
        "age_seconds": age,
    }


async def _redis_ping(
    request: Request,
    redis_url: str,
    *,
    registry: DependencyStatusRegistry | None,
    connect_timeout_seconds: float,
    operation_timeout_seconds: float,
) -> dict[str, Any]:
    name = "redis_ping"
    endpoint = parse_redis_endpoint(redis_url)
    client = aioredis.from_url(
        redis_url,
        socket_connect_timeout=connect_timeout_seconds,
        socket_timeout=operation_timeout_seconds,
        health_check_interval=30,
        retry_on_timeout=False,
    )
    try:
        await asyncio.wait_for(client.ping(), timeout=connect_timeout_seconds + operation_timeout_seconds)
        if registry:
            registry.mark_ok(
                name,
                "Redis respondeu ao PING",
                reason_code="pong",
                redis_url=safe_redis_url(redis_url),
                redis_host=endpoint.host,
                redis_port=endpoint.port,
            )
        restart = getattr(request.app.state, "restart_redis_subscriber_if_needed", None)
        if restart is not None:
            restarted = await restart("redis health ping recovered")
            if restarted and registry:
                registry.mark_degraded(
                    "redis_pubsub",
                    "Redis voltou a responder; reiniciando ciclo do subscriber Pub/Sub",
                    reason_code="redis_recovered_restart_requested",
                    phase="restarting",
                )
        return registry.as_dict()[name] if registry else {"status": "ok", "detail": "Redis respondeu ao PING"}
    except Exception as exc:
        reason_code, human_reason = classify_connection_error(exc)
        if registry:
            registry.mark_error(
                name,
                exc,
                detail=human_reason,
                reason_code=reason_code,
                human_reason=human_reason,
                redis_url=safe_redis_url(redis_url),
                redis_host=endpoint.host,
                redis_port=endpoint.port,
            )
            return registry.as_dict()[name]
        return {"status": "error", "detail": human_reason, "reason_code": reason_code, "error_type": type(exc).__name__}
    finally:
        await client.aclose()


async def _postgres_ping(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "PostgreSQL respondeu ao SELECT 1"}
    except Exception as exc:
        return {"status": "error", "detail": f"PostgreSQL não respondeu ao SELECT 1: {exc}", "error_type": type(exc).__name__}
    finally:
        await engine.dispose()


async def _dependency_checks(request: Request) -> dict[str, Any]:
    settings = getattr(request.app.state, "settings", None)
    registry: DependencyStatusRegistry | None = getattr(request.app.state, "dependency_status", None)

    checks: dict[str, Any] = {"snapshot": _snapshot_check(request)}

    if settings:
        postgres_task = asyncio.create_task(_postgres_ping(settings.database_url))
        redis_task = asyncio.create_task(_redis_ping(
            request,
            settings.redis_url,
            registry=registry,
            connect_timeout_seconds=float(getattr(settings, "redis_connect_timeout_seconds", 1.0)),
            operation_timeout_seconds=float(getattr(settings, "redis_operation_timeout_seconds", 1.5)),
        ))
        postgres, redis = await asyncio.gather(postgres_task, redis_task)
        checks["postgres"] = postgres
        checks["redis_ping"] = redis
    else:
        checks["postgres"] = {"status": "not_configured", "detail": "Configurações do Gateway não foram inicializadas."}
        checks["redis_ping"] = {"status": "not_configured", "detail": "Configurações do Gateway não foram inicializadas."}

    runtime = registry.as_dict() if registry else {}
    for name, payload in runtime.items():
        if name == "snapshot":
            checks["snapshot"].update({k: v for k, v in payload.items() if k not in {"status", "detail"}})
            continue
        if name == "redis_ping" and checks.get("redis_ping", {}).get("status") == "ok":
            continue
        checks[name] = payload
    return checks


def _redact_checks(checks: dict[str, Any], *, detailed: bool) -> dict[str, Any]:
    if detailed:
        return checks
    public: dict[str, Any] = {}
    for name in PUBLIC_CHECKS:
        if name in checks:
            item = dict(checks[name])
            if name == "snapshot":
                item = {k: v for k, v in item.items() if k in {"status", "detail", "loaded_at", "last_successful_load_at", "age_seconds"}}
            public[name] = item
    return public


def _overall(checks: dict[str, Any], *, critical: tuple[str, ...], detailed: bool) -> str:
    for name in critical:
        if checks.get(name, {}).get("status") != "ok":
            return "error"
    relevant = checks.values() if detailed else (checks.get(name, {}) for name in PUBLIC_CHECKS)
    statuses = [value.get("status") for value in relevant if value]
    if any(status == "error" for status in statuses):
        return "degraded"
    if any(status in {"degraded", "unknown", "not_loaded", "not_configured", "inactive"} for status in statuses):
        return "degraded"
    return "ok"


async def live_response() -> dict[str, Any]:
    return {"service": "gateway", "status": "ok", "detail": "Processo HTTP do Gateway está vivo.", "checked_at": _now()}


async def ready_response(request: Request) -> dict[str, Any]:
    detailed = _is_superuser_request(request)
    checks = await _dependency_checks(request)
    status = _overall(checks, critical=("snapshot", "postgres"), detailed=detailed)
    snapshot_ok = checks.get("snapshot", {}).get("status") == "ok"
    visible_checks = _redact_checks(checks, detailed=detailed)
    return {
        "service": "gateway",
        "status": status,
        "ready": snapshot_ok and checks.get("postgres", {}).get("status") == "ok",
        "detail": "Gateway pronto; dependências auxiliares podem estar degradadas." if snapshot_ok else "Gateway sem snapshot válida carregada.",
        "checked_at": _now(),
        "scope": "superuser" if detailed else "summary",
        "checks": visible_checks,
    }


async def dependencies_response(request: Request) -> dict[str, Any]:
    detailed = _is_superuser_request(request)
    checks = await _dependency_checks(request)
    status = _overall(checks, critical=("snapshot", "postgres"), detailed=detailed)
    return {
        "service": "gateway",
        "status": status,
        "checked_at": _now(),
        "scope": "superuser" if detailed else "summary",
        "checks": _redact_checks(checks, detailed=detailed),
    }


@router.get("/health/live")
@router.get("/api/v1/health/live", include_in_schema=False)
async def health_live() -> dict[str, Any]:
    return await live_response()


@router.get("/health/ready")
@router.get("/api/v1/health/ready", include_in_schema=False)
async def health_ready(request: Request) -> dict[str, Any]:
    return await ready_response(request)


@router.get("/health/dependencies")
@router.get("/api/v1/health/dependencies", include_in_schema=False)
async def health_dependencies(request: Request) -> dict[str, Any]:
    return await dependencies_response(request)


@router.get("/health")
@router.get("/api/v1/health", include_in_schema=False)
async def health(request: Request) -> dict[str, Any]:
    return await dependencies_response(request)
