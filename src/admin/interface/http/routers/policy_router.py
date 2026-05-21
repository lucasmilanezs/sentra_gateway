from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_policy import ManagePolicy
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_manage_policy, require_permission
from src.admin.interface.schema.policy_schema import PolicyResponse, PolicyUpsert

router = APIRouter(tags=["policies"])


@router.get("/{route_id}/policy", response_model=PolicyResponse | None)
async def get_policy(
    route_id: str,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
):
    return await uc.get_by_route(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
    )


@router.put(
    "/{route_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_policy(
    route_id: str,
    body: PolicyUpsert,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
):
    return await uc.upsert(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
        requires_auth=body.requires_auth,
        rate_limit_per_minute=body.rate_limit_per_minute,
        allowed_roles=body.allowed_roles,
        jwt_validate_exp=body.jwt_validate_exp,
        jwt_issuer=body.jwt_issuer,
        jwt_audience=body.jwt_audience,
        jwt_clock_skew_seconds=body.jwt_clock_skew_seconds,
    )


@router.delete("/{route_id}/policy", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    route_id: str,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
):
    await uc.delete(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
    )
