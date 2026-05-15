from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_policy import ManagePolicy
from src.admin.interface.http.dependencies import get_current_claims, get_manage_policy
from src.admin.interface.schema.policy_schema import PolicyResponse, PolicyUpsert

router = APIRouter(tags=["policies"])


@router.get("/{route_id}/policy", response_model=PolicyResponse | None)
async def get_policy(
    route_id: str,
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
    _: Annotated[object, Depends(get_current_claims)],
):
    return await uc.get_by_route(route_id)


@router.put(
    "/{route_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_policy(
    route_id: str,
    body: PolicyUpsert,
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
    _: Annotated[object, Depends(get_current_claims)],
):
    return await uc.upsert(
        route_id=route_id,
        requires_auth=body.requires_auth,
        rate_limit_per_minute=body.rate_limit_per_minute,
        allowed_roles=body.allowed_roles,
    )


@router.delete("/{route_id}/policy", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    route_id: str,
    uc: Annotated[ManagePolicy, Depends(get_manage_policy)],
    _: Annotated[object, Depends(get_current_claims)],
):
    await uc.delete(route_id)