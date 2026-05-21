from __future__ import annotations
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.admin.application.services.tenant_ownership_guard import TenantOwnershipGuard
from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.exceptions import AuthError, NotFoundError, ValidationError
from src.admin.domain.services.route_validation import validate_path_pattern
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


def _parse_methods(raw: list[str] | list[HttpMethod]) -> list[HttpMethod]:
    result = []
    for m in raw:
        if isinstance(m, HttpMethod):
            result.append(m)
        else:
            try:
                result.append(HttpMethod(str(m).upper()))
            except ValueError:
                raise ValidationError(f"método HTTP inválido: {m}")
    if not result:
        raise ValidationError("pelo menos um método HTTP deve ser informado")
    return result


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

    async def list(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str | None = None,
    ) -> list[AdminRoute]:
        # superuser pode filtrar por qualquer tenant via query param;
        # todos os outros ficam presos ao próprio tenant.
        effective_tenant = (
            tenant_id if caller_role == "superuser" else caller_tenant_id
        )
        return await self._routes.list_all(tenant_id=effective_tenant)

    async def get(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
    ) -> AdminRoute:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=r.tenant_id,
        )
        return r

    async def create(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
        path_pattern: str,
        methods: list[HttpMethod],
        backend_url: str,
    ) -> AdminRoute:
        # superuser pode criar em qualquer tenant via body;
        # admin/member ficam presos ao próprio tenant (body.tenant_id ignorado).
        effective_tenant = (
            tenant_id if caller_role == "superuser" else caller_tenant_id
        )
        if not effective_tenant:
            raise AuthError("caller sem tenant vinculado não pode criar rotas")
        if not await self._tenants.get_by_id(effective_tenant):
            raise NotFoundError("tenant não encontrado")

        path_pattern = validate_path_pattern(path_pattern)
        parsed_methods = _parse_methods(methods)
        _validate_backend_url(backend_url.strip())

        now = _utcnow()
        route = AdminRoute(
            id=str(uuid.uuid4()),
            tenant_id=effective_tenant,
            path_pattern=path_pattern,
            methods=parsed_methods,
            backend_url=backend_url.strip().rstrip("/"),
            created_at=now,
            updated_at=now,
        )
        await self._routes.save(route)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return route

    async def update(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
        data: dict,
    ) -> AdminRoute:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=r.tenant_id,
        )

        new_path = (
            validate_path_pattern(data["path_pattern"]) if "path_pattern" in data else r.path_pattern
        )

        new_url = (
            data["backend_url"].strip().rstrip("/") if "backend_url" in data else r.backend_url
        )
        _validate_backend_url(new_url)

        if "methods" in data:
            new_methods = _parse_methods(data["methods"])
        else:
            new_methods = r.methods

        updated = AdminRoute(
            id=r.id,
            tenant_id=r.tenant_id,
            path_pattern=new_path,
            methods=new_methods,
            backend_url=new_url,
            created_at=r.created_at,
            updated_at=_utcnow(),
        )
        await self._routes.save(updated)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return updated

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
    ) -> None:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=r.tenant_id,
        )
        await self._routes.delete(route_id)

        if self._publisher:
            await self._publisher.notify_config_updated()
