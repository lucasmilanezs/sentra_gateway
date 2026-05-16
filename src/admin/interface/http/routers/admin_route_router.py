from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.interface.http.dependencies import get_current_claims, get_manage_route
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
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    _: Annotated[object, Depends(get_current_claims)],
    tenant_id: str | None = Query(default=None),
):
    items = await uc.list(tenant_id=tenant_id)
    return [_to_response(r) for r in items]


@router.post("", response_model=AdminRouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: AdminRouteCreate,
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    _: Annotated[object, Depends(get_current_claims)],
):
    r = await uc.create(body.tenant_id, body.path_pattern, body.methods, body.backend_url)
    return _to_response(r)


@router.get("/{route_id}", response_model=AdminRouteResponse)
async def get_route(
    route_id: str,
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    _: Annotated[object, Depends(get_current_claims)],
):
    r = await uc.get(route_id)
    return _to_response(r)


@router.patch("/{route_id}", response_model=AdminRouteResponse)
async def patch_route(
    route_id: str,
    body: AdminRouteUpdate,
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    _: Annotated[object, Depends(get_current_claims)],
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
    uc: Annotated[ManageAdminRoute, Depends(get_manage_route)],
    _: Annotated[object, Depends(get_current_claims)],
):
    await uc.delete(route_id)
