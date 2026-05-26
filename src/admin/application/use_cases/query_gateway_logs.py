from __future__ import annotations

from dataclasses import replace

from src.admin.domain.entities.raw_gateway_log import RawGatewayLog
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.raw_gateway_log_repository import RawGatewayLogRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort


class QueryGatewayLogs:
    """Application use case for reading gateway raw operational logs."""

    def __init__(
        self,
        logs: RawGatewayLogRepositoryPort,
        routes: AdminRouteRepositoryPort | None = None,
        tenants: TenantRepositoryPort | None = None,
    ) -> None:
        self._logs = logs
        self._routes = routes
        self._tenants = tenants

    async def list_recent(self, *, tenant_id: str | None, limit: int = 100) -> list[RawGatewayLog]:
        rows = await self._logs.list_recent(tenant_id=tenant_id, limit=min(limit, 500))
        route_labels = await self._route_labels(tenant_id=tenant_id)
        tenant_labels = await self._tenant_labels()
        enriched: list[RawGatewayLog] = []
        for row in rows:
            route_label = route_labels.get(row.route_id or "") or row.path or "rota não resolvida"
            tenant_label = tenant_labels.get(row.tenant_id or "")
            summary = self._semantic_summary(row=row, route_label=route_label)
            enriched.append(replace(row, route_label=route_label, tenant_label=tenant_label, summary=summary))
        return enriched

    async def _route_labels(self, *, tenant_id: str | None) -> dict[str, str]:
        if self._routes is None:
            return {}
        try:
            routes = await self._routes.list_all(tenant_id=tenant_id)
        except Exception:
            return {}
        return {route.id: route.path_pattern for route in routes}

    async def _tenant_labels(self) -> dict[str, str]:
        if self._tenants is None:
            return {}
        try:
            tenants = await self._tenants.list_all()
        except Exception:
            return {}
        return {tenant.id: tenant.name or tenant.alias for tenant in tenants}

    def _semantic_summary(self, *, row: RawGatewayLog, route_label: str) -> str:
        method = row.method or "?"
        path = row.path or route_label or "?"
        status = row.status_code if row.status_code is not None else "?"
        return f"{method} {path} → {status} · {row.outcome}"
