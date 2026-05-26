from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from src.admin.application.use_cases.query_audit import QueryAudit
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_change_audit, get_query_audit, require_permission
from src.admin.interface.schema.audit_schema import (
    AuditFilteredResponse, AuditRequestResponse,
    ChangeEventFilteredResponse, ChangeEventResponse, MetricsSummaryResponse,
)

router = APIRouter()

def _tenant_scope(claims: JwtClaims, tenant_id: str | None) -> str | None:
    if claims.role == "superuser":
        return tenant_id
    return claims.tenant_id

@router.get("/audit", response_model=list[AuditRequestResponse])
async def list_audit(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    uc: Annotated[QueryAudit, Depends(get_query_audit)],
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
):
    scope = _tenant_scope(claims, tenant_id)
    rows = await uc.list_recent(tenant_id=scope, limit=limit)
    return [AuditRequestResponse.model_validate(r) for r in rows]

@router.get("/audit/requests", response_model=AuditFilteredResponse)
async def list_audit_filtered(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    uc: Annotated[QueryAudit, Depends(get_query_audit)],
    tenant_id: str | None = Query(default=None),
    route_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    method: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    scope = _tenant_scope(claims, tenant_id)
    items, total = await uc.list_filtered(tenant_id=scope, route_id=route_id, outcome=outcome, method=method, date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return AuditFilteredResponse(items=[AuditRequestResponse.model_validate(r) for r in items], total=total)

@router.get("/audit/changes", response_model=ChangeEventFilteredResponse)
async def list_change_audit(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    change_audit: Annotated[ChangeAuditRepositoryPort | None, Depends(get_change_audit)],
    tenant_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if change_audit is None:
        return ChangeEventFilteredResponse(items=[], total=0)
    scope = _tenant_scope(claims, tenant_id)
    items, total = await change_audit.list_for_tenant(tenant_id=scope, limit=limit, offset=offset, resource_type=resource_type, action=action)
    return ChangeEventFilteredResponse(items=[ChangeEventResponse.model_validate(r) for r in items], total=total)

@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(
    claims: Annotated[JwtClaims, Depends(require_permission("metrics"))],
    uc: Annotated[QueryAudit, Depends(get_query_audit)],
    tenant_id: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
):
    scope = _tenant_scope(claims, tenant_id)
    data = await uc.metrics_summary(tenant_id=scope, hours=hours)
    return MetricsSummaryResponse(**data)
