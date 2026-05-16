"""
PostgresSnapshotRepository

Carrega rotas, políticas, tenant domains e domain policies do plano Admin
ao startup do Gateway e os serve a partir de um snapshot em memória.

Multi-tenant: cada requisição é resolvida por Host header →
admin_tenant_domains → tenant_id → filtra rotas pelo tenant.
"""

import logging
from typing import Dict, List, Optional, Tuple

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


def _parse_methods(raw: str) -> Tuple[HttpMethod, ...]:
    result = []
    for m in raw.split(","):
        m = m.strip().upper()
        if not m:
            continue
        try:
            result.append(HttpMethod(m))
        except ValueError:
            logger.warning("Método inválido ignorado no snapshot: %s", m)
    return tuple(result)


class PostgresSnapshotRepository(
    RouteRepository, DomainRepository, PolicyRepository, TenantRepository
):
    """
    Implementação única que satisfaz RouteRepository, DomainRepository,
    PolicyRepository e TenantRepository a partir de um snapshot do Postgres.
    """

    def __init__(self) -> None:
        self._routes: List[Route] = []
        self._domains: Dict[str, Domain] = {}
        self._policies: Dict[str, Policy] = {}          # route_id → Policy
        self._domain_policies: Dict[str, Policy] = {}   # tenant_id → domain global Policy
        self._tenant_by_domain: Dict[str, GatewayTenant] = {}  # domain → GatewayTenant

    async def load(self, database_url: str) -> None:
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:

                # 1. Tenant domains — base do roteamento multi-tenant
                tenant_domain_rows = (await conn.execute(text(
                    "SELECT td.id, td.tenant_id, td.domain "
                    "FROM admin_tenant_domains td"
                ))).fetchall()

                # 2. Rotas — ordenadas por comprimento desc para longest-prefix
                route_rows = (await conn.execute(text(
                    "SELECT id, tenant_id, path_pattern, methods, backend_url "
                    "FROM admin_routes "
                    "ORDER BY length(path_pattern) DESC"
                ))).fetchall()

                # 3. Políticas por rota
                policy_rows = (await conn.execute(text(
                    "SELECT id, route_id, requires_auth, "
                    "rate_limit_per_minute, allowed_roles "
                    "FROM admin_policies"
                ))).fetchall()

                # 4. Políticas globais por domain (domain policy fallback)
                domain_policy_rows = (await conn.execute(text(
                    "SELECT dp.id, td.tenant_id, dp.requires_auth, "
                    "dp.rate_limit_per_minute, dp.allowed_roles "
                    "FROM admin_domain_policies dp "
                    "JOIN admin_tenant_domains td ON td.id = dp.domain_id"
                ))).fetchall()

        finally:
            await engine.dispose()

        # ── Monta índice domain → GatewayTenant ──────────────────────────
        tenant_by_domain: Dict[str, GatewayTenant] = {}
        for row in tenant_domain_rows:
            domain_id, tenant_id, domain = row
            tenant_by_domain[domain] = GatewayTenant(id=tenant_id, domain=domain)

        # ── Monta rotas + domains sintéticos ─────────────────────────────
        routes: List[Route] = []
        domains: Dict[str, Domain] = {}

        for row in route_rows:
            route_id, tenant_id, path_pattern, methods_raw, backend_url = row
            domain_id = f"domain-{route_id}"
            methods = _parse_methods(methods_raw)

            routes.append(Route(
                id=route_id,
                tenant_id=tenant_id,
                path_prefix=path_pattern,
                domain_id=domain_id,
                methods=methods,
            ))
            domains[domain_id] = Domain(
                id=domain_id,
                name=f"backend-{route_id}",
                backend_url=BackendUrl(backend_url),
            )

        # ── Políticas por rota ────────────────────────────────────────────
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

        # ── Domain policies (global fallback por tenant) ──────────────────
        domain_policies: Dict[str, Policy] = {}
        for row in domain_policy_rows:
            gp_id, tenant_id, requires_auth, rate_limit_per_minute, allowed_roles = row
            # Reutiliza Policy com route_id vazio — gateway só lê campos de controle
            domain_policies[tenant_id] = Policy(
                id=gp_id,
                route_id="",
                requires_auth=bool(requires_auth),
                rate_limit_per_minute=rate_limit_per_minute,
                allowed_roles=tuple(r for r in allowed_roles.split(",") if r) if allowed_roles else (),
            )

        # Atribuição atômica
        self._tenant_by_domain = tenant_by_domain
        self._routes = routes
        self._domains = domains
        self._policies = policies
        self._domain_policies = domain_policies

        logger.info(
            "Gateway snapshot: %d domain(s), %d rota(s), %d política(s), %d política(s) global(is).",
            len(self._tenant_by_domain),
            len(self._routes),
            len(self._policies),
            len(self._domain_policies),
        )

    async def reload(self, database_url: str) -> None:
        await self.load(database_url)

    # ── TenantRepository ─────────────────────────────────────────────────

    async def get_by_domain(self, host: str) -> Optional[GatewayTenant]:
        clean = host.split(":")[0]
        return self._tenant_by_domain.get(clean)

    # ── RouteRepository ──────────────────────────────────────────────────

    async def get_by_path(self, path: str, method: str, tenant_id: str) -> Optional[Route]:
        for route in self._routes:
            if route.tenant_id == tenant_id and route.matches(path, method):
                return route
        return None

    async def list_all(self) -> List[Route]:
        return list(self._routes)

    # ── DomainRepository ─────────────────────────────────────────────────

    async def get_by_id(self, domain_id: str) -> Optional[Domain]:
        return self._domains.get(domain_id)

    # ── PolicyRepository ─────────────────────────────────────────────────

    async def get_by_route_id(self, route_id: str) -> Optional[Policy]:
        return self._policies.get(route_id)

    def get_domain_policy(self, tenant_id: str) -> Optional[Policy]:
        """Política global do tenant — fallback quando rota não tem Policy própria."""
        return self._domain_policies.get(tenant_id)
