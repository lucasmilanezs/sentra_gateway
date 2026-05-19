from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.admin.application.use_cases.query_audit import QueryAudit
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_query_audit, require_permission
from src.admin.interface.schema.audit_schema import AuditRequestResponse, MetricsSummaryResponse

router = APIRouter()


def _tenant_scope(claims: JwtClaims, tenant_id: str | None) -> str | None:
    if claims.role in ("superuser",) or (claims.role == "admin" and not claims.tenant_id):
        return tenant_id
    return claims.tenant_id


@router.get("/audit", response_model=list[AuditRequestResponse])
async def list_audit(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    uc: Annotated[QueryAudit, Depends(get_query_audit)],
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[AuditRequestResponse]:
    scope = _tenant_scope(claims, tenant_id)
    rows = await uc.list_recent(tenant_id=scope, limit=limit)
    return [AuditRequestResponse.model_validate(r) for r in rows]


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(
    claims: Annotated[JwtClaims, Depends(require_permission("metrics"))],
    uc: Annotated[QueryAudit, Depends(get_query_audit)],
    tenant_id: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
) -> MetricsSummaryResponse:
    scope = _tenant_scope(claims, tenant_id)
    data = await uc.metrics_summary(tenant_id=scope, hours=hours)
    return MetricsSummaryResponse(**data)