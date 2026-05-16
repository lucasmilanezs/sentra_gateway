from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_global_policy import ManageGlobalPolicy
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import (
    get_current_claims,
    get_manage_global_policy,
    require_own_tenant,
)
from src.admin.interface.schema.policy_schema import PolicyResponse

router = APIRouter(tags=["global-policies"])


class GlobalPolicyResponse(PolicyResponse):
    """Response de política global — substitui route_id por tenant_id."""
    route_id: str = ""  # ignorado; mantido para compatibilidade com PolicyResponse
    tenant_id: str = ""


@router.get("/{tenant_id}/policy", response_model=GlobalPolicyResponse | None)
async def get_global_policy(
    tenant_id: str,
    uc: Annotated[ManageGlobalPolicy, Depends(get_manage_global_policy)],
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
):
    require_own_tenant(claims, tenant_id)
    return await uc.get_by_tenant(tenant_id)


@router.put(
    "/{tenant_id}/policy",
    response_model=GlobalPolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_global_policy(
    tenant_id: str,
    body: "PolicyUpsert",
    uc: Annotated[ManageGlobalPolicy, Depends(get_manage_global_policy)],
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
):
    require_own_tenant(claims, tenant_id)
    return await uc.upsert(
        tenant_id=tenant_id,
        requires_auth=body.requires_auth,
        rate_limit_per_minute=body.rate_limit_per_minute,
        allowed_roles=body.allowed_roles,
    )


@router.delete("/{tenant_id}/policy", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_policy(
    tenant_id: str,
    uc: Annotated[ManageGlobalPolicy, Depends(get_manage_global_policy)],
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
):
    require_own_tenant(claims, tenant_id)
    await uc.delete(tenant_id)


# Import tardio para evitar ciclo
from src.admin.interface.schema.policy_schema import PolicyUpsert  # noqa: E402