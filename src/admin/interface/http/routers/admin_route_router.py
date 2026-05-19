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
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=list[AdminRouteResponse])
async def list_routes(
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    tenant_id: str | None = Query(default=None),
):
    # members e admins com tenant só enxergam rotas do próprio tenant
    effective_tenant = claims.tenant_id or tenant_id
    items = await uc.list(tenant_id=effective_tenant)
    return [_to_response(r) for r in items]


@router.post("", response_model=AdminRouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: AdminRouteCreate,
    claims: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    r = await uc.create(body.tenant_id, body.path_pattern, body.methods, body.backend_url)
    return _to_response(r)


@router.get("/{route_id}", response_model=AdminRouteResponse)
async def get_route(
    route_id: str,
    _: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    r = await uc.get(route_id)
    return _to_response(r)


@router.patch("/{route_id}", response_model=AdminRouteResponse)
async def patch_route(
    route_id: str,
    body: AdminRouteUpdate,
    _: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        r = await uc.get(route_id)
        return _to_response(r)
    r = await uc.update(route_id, data)
    return _to_response(r)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: str,
    _: Annotated[JwtClaims, Depends(require_permission("routes"))],
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
):
    await uc.delete(route_id)