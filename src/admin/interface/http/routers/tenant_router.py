from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.application.use_cases.manage_tenant_domain import ManageTenantDomain
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import (
    get_manage_tenant,
    get_manage_tenant_domain,
    require_admin,
    require_permission,
    require_superuser,
)

from src.admin.interface.schema.tenant_schema import (
    DomainPolicyResponse,
    DomainPolicyUpsert,
    DomainSuggestionsResponse,
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
        alias=t.alias,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ── Tenant CRUD — restrito a admin/superuser ──────────────────────────────

@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    _: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):
    items = await uc.list()
    return [_to_response(t) for t in items]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    _: Annotated[JwtClaims, Depends(require_superuser())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):
    t = await uc.create(body.name, body.alias)
    return _to_response(t)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    _: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):
    t = await uc.get(tenant_id)
    return _to_response(t)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def patch_tenant(
    tenant_id: str,
    body: TenantUpdate,
    _: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        t = await uc.get(tenant_id)
        return _to_response(t)
    t = await uc.update(tenant_id, data)
    return _to_response(t)


@router.get("/{tenant_id}/domain-suggestions", response_model=DomainSuggestionsResponse)
async def domain_suggestions(
    tenant_id: str,
    _: Annotated[JwtClaims, Depends(require_admin())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):
    t = await uc.get(tenant_id)
    suggestions = [
        f"api.{t.alias}.local",
        f"gateway.{t.alias}.corp",
        f"{t.alias}.internal",
    ]
    return DomainSuggestionsResponse(
        suggestions=suggestions,
        group_label=f"{t.name} ({t.alias})",
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    _: Annotated[JwtClaims, Depends(require_superuser())],
    uc: Annotated[ManageTenant, Depends(get_manage_tenant)],
):

    await uc.delete(tenant_id)


# ── TenantDomain — requer permissão "domains" ────────────────────────────

@router.get("/{tenant_id}/domains", response_model=list[TenantDomainResponse])
async def list_domains(
    tenant_id: str,
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
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
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
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
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
):
    await uc.delete(domain_id)


# ── DomainPolicy — requer permissão "domains" ────────────────────────────

@router.get(
    "/{tenant_id}/domains/{domain_id}/policy",
    response_model=DomainPolicyResponse | None,
)
async def get_domain_policy(
    tenant_id: str,
    domain_id: str,
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
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
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
):
    p = await uc.upsert_policy(
        domain_id=domain_id,
        requires_auth=body.requires_auth,
        rate_limit_per_minute=body.rate_limit_per_minute,
        allowed_roles=body.allowed_roles,
        jwt_validate_exp=body.jwt_validate_exp,
        jwt_issuer=body.jwt_issuer,
        jwt_audience=body.jwt_audience,
        jwt_clock_skew_seconds=body.jwt_clock_skew_seconds,
    )
    return DomainPolicyResponse.model_validate(p)


@router.delete(
    "/{tenant_id}/domains/{domain_id}/policy",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_domain_policy(
    tenant_id: str,
    domain_id: str,
    _: Annotated[JwtClaims, Depends(require_permission("domains"))],
    uc: Annotated[ManageTenantDomain, Depends(get_manage_tenant_domain)],
):
    await uc.delete_policy(domain_id)