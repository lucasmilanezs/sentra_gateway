import re
import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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

    def _validate_slug(self, slug: str) -> None:
        if not slug or len(slug) > 128:
            raise ValidationError("slug inválido")
        if not _SLUG_RE.match(slug):
            raise ValidationError("slug deve conter apenas letras minúsculas, números e hífens")

    async def list(self) -> list[Tenant]:
        return await self._tenants.list_all()

    async def get(self, tenant_id: str) -> Tenant:
        t = await self._tenants.get_by_id(tenant_id)
        if not t:
            raise NotFoundError("tenant não encontrado")
        return t

    async def create(self, name: str, slug: str) -> Tenant:
        self._validate_slug(slug)
        if await self._tenants.get_by_slug(slug):
            raise ConflictError("slug já em uso")
        now = _utcnow()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name.strip(),
            slug=slug,
            created_at=now,
            updated_at=now,
        )
        await self._tenants.save(tenant)
        return tenant

    async def update(self, tenant_id: str, data: dict) -> Tenant:
        t = await self._tenants.get_by_id(tenant_id)
        if not t:
            raise NotFoundError("tenant não encontrado")
        new_name = data["name"].strip() if "name" in data else t.name
        new_slug = data["slug"] if "slug" in data else t.slug
        if "slug" in data:
            self._validate_slug(new_slug)
        if new_slug != t.slug:
            existing = await self._tenants.get_by_slug(new_slug)
            if existing and existing.id != tenant_id:
                raise ConflictError("slug já em uso")
        updated = Tenant(
            id=t.id,
            name=new_name,
            slug=new_slug,
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
