from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.admin.application.services.governance_audit_recorder import GovernanceAuditRecorder
from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.exceptions import NotFoundError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.value_objects.http_method import HttpMethod


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        self._audit = GovernanceAuditRecorder(change_audit)

    async def list(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str | None = None,
    ) -> list[AdminRoute]:
        effective_tenant = TenantAccessControl.resolve_read_scope(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            requested_tenant_id=tenant_id,
        )
        return await self._routes.list_all(tenant_id=effective_tenant)

    async def get(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
    ) -> AdminRoute:
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        return route

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
        effective_tenant = TenantAccessControl.resolve_write_scope(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            requested_tenant_id=tenant_id,
        )
        if not await self._tenants.get_by_id(effective_tenant):
            raise NotFoundError("tenant não encontrado")

        now = _utcnow()
        route = AdminRoute.create(
            id=str(uuid.uuid4()),
            tenant_id=effective_tenant,
            path_pattern=path_pattern,
            methods=methods,
            backend_url=backend_url,
            now=now,
        )
        await self._routes.save(route)
        await self._audit.record(
            tenant_id=route.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="CREATE",
            resource_type="route",
            resource_id=route.id,
            resource_summary=route.audit_summary(),
            detail=route.audit_detail(),
        )
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
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )

        updated = route.with_updates(data=data, now=_utcnow())
        await self._routes.save(updated)
        await self._audit.record(
            tenant_id=updated.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="UPDATE",
            resource_type="route",
            resource_id=updated.id,
            resource_summary=updated.audit_summary(),
            detail=updated.audit_detail(changed_fields=list(data.keys())),
        )
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
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        await self._routes.delete(route_id)
        await self._audit.record(
            tenant_id=route.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="DELETE",
            resource_type="route",
            resource_id=route.id,
            resource_summary=route.audit_summary(),
            detail=route.audit_detail(),
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
