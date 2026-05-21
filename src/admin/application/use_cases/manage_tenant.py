import re
import uuid
from datetime import datetime, timezone

from src.admin.application.services.tenant_ownership_guard import TenantOwnershipGuard
from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort

_alias_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManageTenant:
    def __init__(
        self,
        tenants: TenantRepositoryPort,
        routes: AdminRouteRepositoryPort,
    ) -> None:
        self._tenants = tenants
        self._routes = routes

    def _validate_alias(self, alias: str) -> None:
        if not alias or len(alias) > 128:
            raise ValidationError("alias inválido")
        if not _alias_RE.match(alias):
            raise ValidationError("alias deve conter apenas letras minúsculas, números e hífens")

    async def list(self) -> list[Tenant]:
        return await self._tenants.list_all()

    async def get(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
    ) -> Tenant:
        t = await self._tenants.get_by_id(tenant_id)
        if not t:
            raise NotFoundError("tenant não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=t.id,
        )
        return t

    async def create(self, name: str, alias: str) -> Tenant:
        self._validate_alias(alias)
        if await self._tenants.get_by_alias(alias):
            raise ConflictError("alias já em uso")
        now = _utcnow()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name.strip(),
            alias=alias,
            created_at=now,
            updated_at=now,
        )
        await self._tenants.save(tenant)
        return tenant

    async def update(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
        data: dict,
    ) -> Tenant:
        t = await self._tenants.get_by_id(tenant_id)
        if not t:
            raise NotFoundError("tenant não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=t.id,
        )
        new_name = data["name"].strip() if "name" in data else t.name
        new_alias = data["alias"] if "alias" in data else t.alias
        if "alias" in data:
            self._validate_alias(new_alias)
        if new_alias != t.alias:
            existing = await self._tenants.get_by_alias(new_alias)
            if existing and existing.id != tenant_id:
                raise ConflictError("alias já em uso")
        updated = Tenant(
            id=t.id,
            name=new_name,
            alias=new_alias,
            created_at=t.created_at,
            updated_at=_utcnow(),
        )
        await self._tenants.save(updated)
        return updated

    async def delete(self, tenant_id: str) -> None:
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        linked = await self._routes.list_all(tenant_id=tenant_id)
        if linked:
            raise ConflictError("existem rotas vinculadas a este tenant; remova-as antes")
        if not await self._tenants.delete(tenant_id):
            raise NotFoundError("tenant não encontrado")
