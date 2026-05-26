from __future__ import annotations
import uuid
from datetime import datetime, timezone
from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.exceptions import AuthError, NotFoundError, ValidationError
from src.admin.domain.services.route_validation import validate_backend_url, validate_path_pattern
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.value_objects.http_method import HttpMethod
from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        publisher: ConfigNotifier | None = None,
        change_audit: ChangeAuditRepositoryPort | None = None,
    ) -> None:
        self._routes = routes
        self._tenants = tenants
        self._publisher = publisher
        self._change_audit = change_audit

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
        TenantAccessControl.ensure_tenant_access(
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
        caller_user_id: str | None = None,
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
        backend_url = validate_backend_url(backend_url)

        now = _utcnow()
        route = AdminRoute(
            id=str(uuid.uuid4()),
            tenant_id=effective_tenant,
            path_pattern=path_pattern,
            methods=parsed_methods,
            backend_url=backend_url,
            created_at=now,
            updated_at=now,
        )
        await self._routes.save(route)
        await self._record_change(tenant_id=route.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="CREATE", resource_type="route", resource_id=route.id, resource_summary=route.path_pattern, detail={"methods": [m.value for m in route.methods], "backend_url": route.backend_url})

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
        caller_user_id: str | None = None,
    ) -> AdminRoute:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=r.tenant_id,
        )

        new_path = (
            validate_path_pattern(data["path_pattern"]) if "path_pattern" in data else r.path_pattern
        )

        new_url = (
            validate_backend_url(data["backend_url"]) if "backend_url" in data else r.backend_url
        )

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
        await self._record_change(tenant_id=updated.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="UPDATE", resource_type="route", resource_id=updated.id, resource_summary=updated.path_pattern, detail={"changed_fields": sorted(data.keys()), "methods": [m.value for m in updated.methods], "backend_url": updated.backend_url})

        if self._publisher:
            await self._publisher.notify_config_updated()

        return updated

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
        caller_user_id: str | None = None,
    ) -> None:
        r = await self._routes.get_by_id(route_id)
        if not r:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=r.tenant_id,
        )
        await self._routes.delete(route_id)
        await self._record_change(tenant_id=r.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="DELETE", resource_type="route", resource_id=r.id, resource_summary=r.path_pattern, detail={"backend_url": r.backend_url})

        if self._publisher:
            await self._publisher.notify_config_updated()

    async def _record_change(self, *, tenant_id, actor_id, actor_role, action, resource_type, resource_id, resource_summary, detail=None):
        if not self._change_audit:
            return
        await self._change_audit.record(GovernanceAuditEventFactory.build(tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role or "unknown", action=action, resource_type=resource_type, resource_id=resource_id, resource_summary=resource_summary, detail=detail))
