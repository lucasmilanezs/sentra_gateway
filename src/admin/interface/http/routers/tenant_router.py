from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.interface.http.dependencies import get_current_claims, get_manage_tenant
from src.admin.interface.schema.tenant_schema import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _to_response(t) -> TenantResponse:
    return TenantResponse(
        id=t.id,
        name=t.name,
        slug=t.slug,
        domain=t.domain,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
    _: Annotated[object, Depends(get_current_claims)],
):
    items = await uc.list()
    return [_to_response(t) for t in items]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
    _: Annotated[object, Depends(get_current_claims)],
):
    t = await uc.create(body.name, body.slug, body.domain)
    return _to_response(t)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
    _: Annotated[object, Depends(get_current_claims)],
):
    t = await uc.get(tenant_id)
    return _to_response(t)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def patch_tenant(
    tenant_id: str,
    body: TenantUpdate,
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
    _: Annotated[object, Depends(get_current_claims)],
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        t = await uc.get(tenant_id)
        return _to_response(t)
    t = await uc.update(tenant_id, data)
    return _to_response(t)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
    _: Annotated[object, Depends(get_current_claims)],
):
    await uc.delete(tenant_id)
