from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.application.use_cases.manage_tenant_domain import ManageTenantDomain
from src.admin.interface.http.dependencies import (
    get_current_claims,
    get_manage_tenant,
    get_manage_tenant_domain,
)
from src.admin.interface.schema.tenant_schema import (
    DomainPolicyResponse,
    DomainPolicyUpsert,
    TenantCreate,
    TenantDomainCreate,
    TenantDomainResponse,
    TenantResponse,
    TenantUpdate,
)

router = APIRouter(tags=["tenants"])


def _to_response(t) -> TenantResponse:
    return TenantResponse(
        id=t.id,
        name=t.name,
        slug=t.slug,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ── Tenant CRUD ──────────────────────────────────────────────────────────

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
    t = await uc.create(body.name, body.slug)
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


# ── TenantDomain sub-resource ────────────────────────────────────────────

@router.get("/{tenant_id}/domains", response_model=list[TenantDomainResponse])
async def list_domains(
    tenant_id: str,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    items = await uc.list(tenant_id)
    return [TenantDomainResponse(
        id=d.id, tenant_id=d.tenant_id, domain=d.domain,
        created_at=d.created_at, updated_at=d.updated_at,
    ) for d in items]


@router.post(
    "/{tenant_id}/domains",
    response_model=TenantDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_domain(
    tenant_id: str,
    body: TenantDomainCreate,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    d = await uc.create(tenant_id, body.domain)
    return TenantDomainResponse(
        id=d.id, tenant_id=d.tenant_id, domain=d.domain,
        created_at=d.created_at, updated_at=d.updated_at,
    )


@router.delete("/{tenant_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    tenant_id: str,
    domain_id: str,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    await uc.delete(domain_id)


# ── DomainPolicy sub-resource ────────────────────────────────────────────

@router.get(
    "/{tenant_id}/domains/{domain_id}/policy",
    response_model=DomainPolicyResponse | None,
)
async def get_domain_policy(
    tenant_id: str,
    domain_id: str,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    return await uc.get_policy(domain_id)


@router.put(
    "/{tenant_id}/domains/{domain_id}/policy",
    response_model=DomainPolicyResponse,
)
async def upsert_domain_policy(
    tenant_id: str,
    domain_id: str,
    body: DomainPolicyUpsert,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    p = await uc.upsert_policy(
        domain_id=domain_id,
        requires_auth=body.requires_auth,
        rate_limit_per_minute=body.rate_limit_per_minute,
        allowed_roles=body.allowed_roles,
    )
    return DomainPolicyResponse(
        id=p.id, domain_id=p.domain_id, requires_auth=p.requires_auth,
        rate_limit_per_minute=p.rate_limit_per_minute, allowed_roles=p.allowed_roles,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.delete(
    "/{tenant_id}/domains/{domain_id}/policy",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_domain_policy(
    tenant_id: str,
    domain_id: str,
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
    _: Annotated[object, Depends(get_current_claims)],
):
    await uc.delete_policy(domain_id)
