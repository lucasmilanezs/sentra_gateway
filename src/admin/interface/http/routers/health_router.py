from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from src.admin.infrastructure.health.system_health import build_admin_health

router = APIRouter(tags=["health"])


def _admin_from_request(request: Request):
    return getattr(request.app.state, "admin", None)


async def _admin_health_response(request: Request) -> dict[str, Any]:
    admin = _admin_from_request(request)
    if admin is None:
        return {
            "service": "admin",
            "status": "error",
            "ready": False,
            "detail": "admin wiring não está configurado",
            "postgres_connected": False,
            "redis_connected": False,
            "checks": {"admin": {"status": "error", "detail": "admin wiring não está configurado"}},
        }
    return await build_admin_health(admin)


@router.get("/health/live")
@router.get("/api/v1/health/live", include_in_schema=False)
async def health_live() -> dict[str, Any]:
    return {"service": "admin", "status": "ok", "detail": "processo HTTP do admin está vivo"}


@router.get("/health/ready")
@router.get("/api/v1/health/ready", include_in_schema=False)
async def health_ready(request: Request) -> dict[str, Any]:
    return await _admin_health_response(request)


@router.get("/health/dependencies")
@router.get("/api/v1/health/dependencies", include_in_schema=False)
async def health_dependencies(request: Request) -> dict[str, Any]:
    return await _admin_health_response(request)


@router.get("/health")
@router.get("/api/v1/health", include_in_schema=False)
async def health(request: Request) -> dict[str, Any]:
    return await _admin_health_response(request)
