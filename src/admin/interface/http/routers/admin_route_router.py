from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_manage_route, require_permission
from src.admin.interface.schema.route_schema import (
    AdminRouteCreate,
    AdminRouteResponse,
    AdminRouteUpdate,
)

router = APIRouter(tags=["routes"])


def _to_response(r) -> AdminRouteResponse:
    return AdminRouteResponse(
        id=r.id,
        tenant_id=r.tenant_id,
        path_pattern=r.path_pattern,
        methods=r.methods,
        backend_url=r.backend_url,
        display_color=r.display_color,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=list[AdminRouteResponse])
async def list_routes(
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    tenant_id: str | None = Query(default=None),
):
    items = await uc.list(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        tenant_id=tenant_id,
    )
    return [_to_response(r) for r in items]


@router.post("", response_model=AdminRouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: AdminRouteCreate,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    r = await uc.create(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        tenant_id=body.tenant_id,
        path_pattern=body.path_pattern,
        methods=body.methods,
        backend_url=body.backend_url,
        display_color=body.display_color,
        caller_user_id=claims.sub,
    )
    return _to_response(r)


@router.get("/{route_id}", response_model=AdminRouteResponse)
async def get_route(
    route_id: str,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    r = await uc.get(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
    )
    return _to_response(r)


@router.patch("/{route_id}", response_model=AdminRouteResponse)
async def patch_route(
    route_id: str,
    body: AdminRouteUpdate,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        r = await uc.get(
            caller_role=claims.role,
            caller_tenant_id=claims.tenant_id,
            route_id=route_id,
        )
        return _to_response(r)
    r = await uc.update(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
        data=data,
        caller_user_id=claims.sub,
    )
    return _to_response(r)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: str,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    await uc.delete(
        caller_role=claims.role,
        caller_tenant_id=claims.tenant_id,
        route_id=route_id,
        caller_user_id=claims.sub,
    )
