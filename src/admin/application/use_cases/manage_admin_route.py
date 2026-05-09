import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.exceptions import NotFoundError, ValidationError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.value_objects.http_method import HttpMethod
from src.admin.infrastructure.pubsub.redis_publisher import RedisPublisher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_backend_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValidationError("backend_url deve ser uma URL http(s) válida")


class ManageAdminRoute:
    def __init__(
        self,
        routes: AdminRouteRepositoryPort,
        tenants: TenantRepositoryPort,
        publisher: RedisPublisher | None = None,
    ) -> None:
        self._routes = routes
        self._tenants = tenants
        self._publisher = publisher

    async def list(self, tenant_id: str | None = None) -> list[AdminRoute]:
        return await self._routes.list_all(tenant_id=tenant_id)

    async def get(self, route_id: str) -> AdminRoute:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        return r

    async def create(
        self,
        tenant_id: str,
        path_pattern: str,
        method: HttpMethod,
        backend_url: str,
    ) -> AdminRoute:
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        path_pattern = path_pattern.strip()
        if not path_pattern.startswith("/"):
            raise ValidationError("path_pattern deve começar com /")
        _validate_backend_url(backend_url.strip())
        now = _utcnow()
        route = AdminRoute(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            path_pattern=path_pattern,
            method=method,
            backend_url=backend_url.strip().rstrip("/"),
            created_at=now,
            updated_at=now,
        )
        await self._routes.save(route)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return route

    async def update(self, route_id: str, data: dict) -> AdminRoute:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        new_path = data["path_pattern"].strip() if "path_pattern" in data else r.path_pattern
        if not new_path.startswith("/"):
            raise ValidationError("path_pattern deve começar com /")
        new_url = (
            data["backend_url"].strip().rstrip("/") if "backend_url" in data else r.backend_url
        )
        _validate_backend_url(new_url)
        new_method = data["method"] if "method" in data else r.method
        if isinstance(new_method, str):
            new_method = HttpMethod(new_method.upper())
        updated = AdminRoute(
            id=r.id,
            tenant_id=r.tenant_id,
            path_pattern=new_path,
            method=new_method,
            backend_url=new_url,
            created_at=r.created_at,
            updated_at=_utcnow(),
        )
        await self._routes.save(updated)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return updated

    async def delete(self, route_id: str) -> None:
        if not await self._routes.delete(route_id):
            raise NotFoundError("rota não encontrada")

        if self._publisher:
            await self._publisher.notify_config_updated()