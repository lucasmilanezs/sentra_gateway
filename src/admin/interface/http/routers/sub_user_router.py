from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_sub_user import ManageSubUser
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_manage_sub_user, require_admin
from src.admin.interface.schema.sub_user_schema import (
    SubUserCreate,
    SubUserResponse,
    SubUserUpdatePermissions,
)

router = APIRouter(tags=["sub-users"])


def _to_response(u) -> SubUserResponse:
    return SubUserResponse(
        id=u.id,
        email=u.email,
        tenant_id=u.tenant_id,
        role=u.role,
        permissions=u.permissions,
        created_at=u.created_at,
    )


@router.post("", response_model=SubUserResponse, status_code=status.HTTP_201_CREATED)
async def create_sub_user(
    body: SubUserCreate,
    claims: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageSubUser, Depends(get_manage_sub_user)],
):
    user = await uc.create(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        email=body.email,
        password=body.password,
        permissions=body.permissions,
        target_tenant_id=body.tenant_id,  # só usado por superuser
    )
    return _to_response(user)


@router.get("/{tenant_id}", response_model=list[SubUserResponse])
async def list_sub_users(
    tenant_id: str,
    claims: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageSubUser, Depends(get_manage_sub_user)],
):
    users = await uc.list_by_tenant(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        tenant_id=tenant_id,
    )
    return [_to_response(u) for u in users]


@router.patch("/{user_id}/permissions", response_model=SubUserResponse)
async def update_permissions(
    user_id: str,
    body: SubUserUpdatePermissions,
    claims: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageSubUser, Depends(get_manage_sub_user)],
):
    user = await uc.update_permissions(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        user_id=user_id,
        permissions=body.permissions,
    )
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_user(
    user_id: str,
    claims: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageSubUser, Depends(get_manage_sub_user)],
):
    await uc.delete(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        user_id=user_id,
    )