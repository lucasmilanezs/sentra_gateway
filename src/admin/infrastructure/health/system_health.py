from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text

from src.shared.runtime.redis_diagnostics import classify_connection_error, parse_redis_endpoint, tcp_probe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_rank(status: str) -> int:
    return {
        "ok": 0,
        "degraded": 1,
        "inactive": 1,
        "unknown": 1,
        "not_configured": 1,
        "not_loaded": 2,
        "error": 2,
    }.get(status, 1)


def aggregate_status(statuses: list[str]) -> str:
    worst = max((_status_rank(s) for s in statuses), default=1)
    if worst >= 2:
        return "error"
    if worst == 1:
        return "degraded"
    return "ok"


def _component(status: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "detail": detail, **{k: v for k, v in extra.items() if v is not None}}


def _gateway_api_status(live: dict[str, Any], ready: dict[str, Any], dependencies: dict[str, Any]) -> str:
    live_status = str(live.get("status", "unknown"))
    ready_status = str(ready.get("status", "unknown"))
    ready_flag = bool(ready.get("ready", False))

    if live_status == "error":
        return "error"
    if live_status != "ok":
        return "degraded"
    if not ready_flag:
        return "error" if ready_status == "error" else "degraded"

    checks = dependencies.get("checks", {}) if isinstance(dependencies, dict) else {}
    for critical in ("snapshot", "postgres"):
        if checks.get(critical, {}).get("status") != "ok":
            return "error"
    return "ok"


def _gateway_api_detail(status: str, checks: dict[str, Any]) -> str:
    snapshot = checks.get("snapshot", {})
    redis = checks.get("redis_ping", {})
    if status == "ok" and redis.get("status") in {"error", "inactive"}:
        return "Gateway operacional com snapshot local; Redis indisponível afeta rate limit, logs operacionais e updates dinâmicos."
    if status == "ok":
        return "Gateway vivo, pronto e com dependências críticas saudáveis."
    if snapshot.get("status") != "ok":
        return "Gateway não possui snapshot válida carregada."
    return "Gateway vivo, mas com readiness ou dependências críticas degradadas."


async def check_postgres(session_factory) -> dict[str, Any]:
    if not session_factory:
        return _component("not_configured", "Factory de sessão PostgreSQL do Admin não está configurada.")
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return _component("ok", "PostgreSQL do Admin respondeu ao SELECT 1.")
    except Exception as exc:
        return _component("error", f"PostgreSQL do Admin não respondeu ao SELECT 1: {exc}", error_type=type(exc).__name__)


async def check_redis(settings) -> dict[str, Any]:
    if settings is None:
        return _component("not_configured", "Configurações Redis do Admin não estão disponíveis.")
    try:
        endpoint = parse_redis_endpoint(settings.redis_url)
        await tcp_probe(endpoint.host, endpoint.port, timeout=float(getattr(settings, "redis_connect_timeout_seconds", 1.0)))
        return _component(
            "ok",
            "Redis do Admin acessível via conexão TCP.",
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
        )


async def fetch_gateway_health(base_url: str, *, timeout: float) -> dict[str, Any]:
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            live_resp = await client.get(f"{base}/health/live")
            live_resp.raise_for_status()
            live = live_resp.json()
        except Exception as exc:
            return _component(
                "error",
                f"Gateway não respondeu ao live check: {exc}",
                error_type=type(exc).__name__,
                base_url=base,
            )

        try:
            ready_resp = await client.get(f"{base}/health/ready")
            ready_resp.raise_for_status()
            ready = ready_resp.json()
        except Exception as exc:
            return _component(
                "degraded",
                f"Gateway está vivo, mas o ready check falhou: {exc}",
                error_type=type(exc).__name__,
                base_url=base,
                live=live,
            )

        try:
            deps_resp = await client.get(f"{base}/health/dependencies")
            deps_resp.raise_for_status()
            dependencies = deps_resp.json()
        except Exception as exc:
            return _component(
                "degraded",
                f"Gateway está pronto, mas o endpoint de dependências falhou: {exc}",
                error_type=type(exc).__name__,
                base_url=base,
                live=live,
                ready=ready,
            )

    checks = dependencies.get("checks", {}) if isinstance(dependencies, dict) else {}
    api_status = _gateway_api_status(live, ready, dependencies)
    dependency_status = aggregate_status([str(dependencies.get("status", "unknown"))])
    return {
        "status": api_status,
        "detail": _gateway_api_detail(api_status, checks),
        "dependency_status": dependency_status,
        "base_url": base,
        "live": live,
        "ready": ready,
        "dependencies": dependencies,
    }


async def build_admin_health(admin, *, include_components: bool = False) -> dict[str, Any]:
    postgres = await check_postgres(getattr(admin, "_session_factory", None))
    redis = await check_redis(getattr(admin, "settings", None))
    if postgres["status"] != "ok":
        status = "error"
        detail = "Admin indisponível: PostgreSQL administrativo não está saudável."
    elif redis["status"] != "ok":
        status = "degraded"
        detail = "Admin operacional, mas Redis de notificação/logs está indisponível."
    else:
        status = "ok"
        detail = "Admin saudável."

    payload: dict[str, Any] = {
        "service": "admin",
        "status": status,
        "detail": detail,
        "scope": "superuser" if include_components else "summary",
        "checked_at": _now(),
        "postgres_connected": postgres.get("status") == "ok",
        "redis_connected": redis.get("status") == "ok",
    }
    if include_components:
        payload["checks"] = {
            "postgres": postgres,
            "redis": redis,
        }
    else:
        payload["checks"] = {
            "postgres": {"status": postgres.get("status"), "detail": postgres.get("detail")},
            "redis": {"status": redis.get("status"), "detail": redis.get("detail")},
        }
    return payload

