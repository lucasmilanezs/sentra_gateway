from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.infrastructure.health.system_health import build_admin_health
from src.admin.interface.http.dependencies import get_current_claims

router = APIRouter(tags=["health"])


def _admin_from_request(request: Request):
    return getattr(request.app.state, "admin", None)


async def _admin_health_response(request: Request, claims: JwtClaims) -> dict[str, Any]:
    admin = _admin_from_request(request)
    if admin is None:
        return {
            "service": "admin",
            "status": "error",
            "scope": "superuser" if claims.role == "superuser" else "summary",
            "postgres_connected": False,
            "checks": {"admin": {"status": "error", "detail": "admin wiring is not configured"}},
        }
    return await build_admin_health(admin, include_components=(claims.role == "superuser"))


@router.get("/health/live")
@router.get("/api/v1/health/live", include_in_schema=False)
async def health_live() -> dict[str, Any]:
    return {"service": "admin", "status": "ok", "detail": "processo HTTP do admin está vivo"}


@router.get("/health/ready")
@router.get("/api/v1/health/ready", include_in_schema=False)
async def health_ready(
    request: Request,
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
) -> dict[str, Any]:
    return await _admin_health_response(request, claims)


@router.get("/health/dependencies")
@router.get("/api/v1/health/dependencies", include_in_schema=False)
async def health_dependencies(
    request: Request,
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
) -> dict[str, Any]:
    return await _admin_health_response(request, claims)


@router.get("/health")
@router.get("/api/v1/health", include_in_schema=False)
async def health(
    request: Request,
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
) -> dict[str, Any]:
    return await _admin_health_response(request, claims)
