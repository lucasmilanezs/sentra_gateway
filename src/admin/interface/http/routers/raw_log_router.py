from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.admin.application.use_cases.query_gateway_logs import QueryGatewayLogs
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_query_gateway_logs, require_permission
from src.admin.interface.schema.audit_schema import RawGatewayLogFilteredResponse, RawGatewayLogResponse

router = APIRouter(tags=["logs"])


def _tenant_scope(claims: JwtClaims, tenant_id: str | None) -> str | None:
    if claims.role == "superuser":
        return tenant_id
    return claims.tenant_id


@router.get("/logs", response_model=RawGatewayLogFilteredResponse)
async def list_gateway_logs(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    uc: Annotated[QueryGatewayLogs, Depends(get_query_gateway_logs)],
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Returns dense short-lived gateway operational logs from Redis Streams.

    This is observability data, not formal governance/request audit evidence.
    Non-superusers are always restricted to their own tenant scope.
    """
    scope = _tenant_scope(claims, tenant_id)
    items = await uc.list_recent(tenant_id=scope, limit=limit)
    return RawGatewayLogFilteredResponse(
        items=[RawGatewayLogResponse(**item.__dict__) for item in items],
        total=len(items),
    )


@router.get("/logs/raw", response_model=RawGatewayLogFilteredResponse)
async def list_gateway_logs_backward_compat(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    uc: Annotated[QueryGatewayLogs, Depends(get_query_gateway_logs)],
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    return await list_gateway_logs(claims=claims, uc=uc, tenant_id=tenant_id, limit=limit)
