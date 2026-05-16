"""
PostgresSnapshotRepository

Carrega rotas, políticas e tenants do plano Admin ao startup do Gateway
e os serve a partir de um snapshot em memória.

Multi-tenant: cada requisição é primeiro resolvida por host (Host header)
para identificar o tenant, depois as rotas são filtradas por tenant_id.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.gateway.domain.models.domain import Domain
from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.route import Route
from src.gateway.domain.ports.domain_repository import DomainRepository
from src.gateway.domain.ports.policy_repository import PolicyRepository
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.domain.ports.tenant_repository import GatewayTenant, TenantRepository
from src.gateway.domain.value_objects.backend_url import BackendUrl
from src.gateway.domain.value_objects.http_method import HttpMethod

logger = logging.getLogger(__name__)


class PostgresSnapshotRepository(
    RouteRepository, DomainRepository, PolicyRepository, TenantRepository
):
    def __init__(self) -> None:
        self._routes: List[Route] = []
        self._domains: Dict[str, Domain] = {}
        self._policies: Dict[str, Policy] = {}          # route_id → Policy
        self._global_policies: Dict[str, Policy] = {}   # tenant_id → Policy (fallback)
        self._tenant_by_domain: Dict[str, GatewayTenant] = {}  # domain → GatewayTenant

    async def load(self, database_url: str) -> None:
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:
                tenant_rows = (await conn.execute(
                    text("SELECT id, domain FROM admin_tenants WHERE domain IS NOT NULL")
                )).fetchall()

                route_rows = (await conn.execute(
                    text(
                        "SELECT id, tenant_id, path_pattern, method, backend_url "
                        "FROM admin_routes "
                        "ORDER BY length(path_pattern) DESC"
                    )
                )).fetchall()

                policy_rows = (await conn.execute(
                    text(
                        "SELECT id, route_id, requires_auth, "
                        "rate_limit_per_minute, allowed_roles "
                        "FROM admin_policies"
                    )
                )).fetchall()

                global_policy_rows = (await conn.execute(
                    text(
                        "SELECT id, tenant_id, requires_auth, "
                        "rate_limit_per_minute, allowed_roles "
                        "FROM admin_global_policies"
                    )
                )).fetchall()
        finally:
            await engine.dispose()

        tenant_by_domain: Dict[str, GatewayTenant] = {}
        for row in tenant_rows:
            tenant_id, domain = row
            tenant_by_domain[domain] = GatewayTenant(id=tenant_id, domain=domain)

        routes: List[Route] = []
        domains: Dict[str, Domain] = {}
        for row in route_rows:
            route_id, tenant_id, path_pattern, method, backend_url = row
            domain_id = f"domain-{route_id}"
            try:
                http_method = HttpMethod(method.upper())
            except ValueError:
                logger.warning("Rota %s ignorada — método inválido: %s", route_id, method)
                continue
            routes.append(Route(
                id=route_id,
                tenant_id=tenant_id,
                path_prefix=path_pattern,
                domain_id=domain_id,
                methods=(http_method,),
            ))
            domains[domain_id] = Domain(
                id=domain_id,
                name=f"backend-{route_id}",
                backend_url=BackendUrl(backend_url),
            )

        policies: Dict[str, Policy] = {}
        for row in policy_rows:
            policy_id, route_id, requires_auth, rate_limit_per_minute, allowed_roles = row
            policies[route_id] = Policy(
                id=policy_id,
                route_id=route_id,
                requires_auth=bool(requires_auth),
                rate_limit_per_minute=rate_limit_per_minute,
                allowed_roles=tuple(r for r in allowed_roles.split(",") if r) if allowed_roles else (),
            )

        global_policies: Dict[str, Policy] = {}
        for row in global_policy_rows:
            gp_id, tenant_id, requires_auth, rate_limit_per_minute, allowed_roles = row
            # Reutiliza Policy com route_id vazio — o gateway só lê os campos de controle
            global_policies[tenant_id] = Policy(
                id=gp_id,
                route_id="",
                requires_auth=bool(requires_auth),
                rate_limit_per_minute=rate_limit_per_minute,
                allowed_roles=tuple(r for r in allowed_roles.split(",") if r) if allowed_roles else (),
            )

        self._tenant_by_domain = tenant_by_domain
        self._routes = routes
        self._domains = domains
        self._policies = policies
        self._global_policies = global_policies

        logger.info(
            "Gateway snapshot: %d tenant(s), %d rota(s), %d política(s), %d política(s) global(is).",
            len(self._tenant_by_domain),
            len(self._routes),
            len(self._policies),
            len(self._global_policies),
        )

    async def reload(self, database_url: str) -> None:
        await self.load(database_url)

    # --- TenantRepository ---

    async def get_by_domain(self, host: str) -> Optional[GatewayTenant]:
        # Strip porta se presente (ex: "api.empresa.com:8000" → "api.empresa.com")
        return self._tenant_by_domain.get(host.split(":")[0])

    # --- RouteRepository ---

    async def get_by_path(self, path: str, method: str, tenant_id: str) -> Optional[Route]:
        for route in self._routes:
            if route.tenant_id == tenant_id and route.matches(path, method):
                return route
        return None

    async def list_all(self) -> List[Route]:
        return list(self._routes)

    # --- DomainRepository ---

    async def get_by_id(self, domain_id: str) -> Optional[Domain]:
        return self._domains.get(domain_id)

    # --- PolicyRepository ---

    async def get_by_route_id(self, route_id: str) -> Optional[Policy]:
        return self._policies.get(route_id)

    def get_global_policy(self, tenant_id: str) -> Optional[Policy]:
        """Política global do tenant — fallback quando rota não tem Policy própria."""
        return self._global_policies.get(tenant_id)