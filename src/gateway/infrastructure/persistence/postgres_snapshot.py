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


def _policy_from_row(
    policy_id: str,
    route_id: str,
    requires_auth,
    rate_limit_per_minute,
    allowed_roles,
    jwt_validate_exp,
    jwt_issuer,
    jwt_audience,
    jwt_clock_skew_seconds,
) -> Policy:
    return Policy(
        id=policy_id,
        route_id=route_id,
        requires_auth=bool(requires_auth),
        rate_limit_per_minute=rate_limit_per_minute,
        allowed_roles=tuple(r for r in allowed_roles.split(",") if r) if allowed_roles else (),
        jwt_validate_exp=bool(jwt_validate_exp) if jwt_validate_exp is not None else True,
        jwt_issuer=jwt_issuer,
        jwt_audience=jwt_audience,
        jwt_clock_skew_seconds=int(jwt_clock_skew_seconds or 30),
    )


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
        self._domain_policies: Dict[str, Policy] = {}   # hostname → domain Policy
        self._tenant_by_domain: Dict[str, GatewayTenant] = {}  # domain → GatewayTenant

    async def load(self, database_url: str) -> None:
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:

                tenant_domain_rows = (await conn.execute(text(
                    "SELECT td.id, td.tenant_id, td.domain "
                    "FROM admin_tenant_domains td"
                ))).fetchall()

                route_rows = (await conn.execute(text(
                    "SELECT id, tenant_id, path_pattern, methods, backend_url "
                    "FROM admin_routes "
                    "ORDER BY length(path_pattern) DESC"
                ))).fetchall()

                policy_rows = (await conn.execute(text(
                    "SELECT id, route_id, requires_auth, "
                    "rate_limit_per_minute, allowed_roles, "
                    "jwt_validate_exp, jwt_issuer, jwt_audience, jwt_clock_skew_seconds "
                    "FROM admin_policies"
                ))).fetchall()

                domain_policy_rows = (await conn.execute(text(
                    "SELECT dp.id, td.domain, dp.requires_auth, "
                    "dp.rate_limit_per_minute, dp.allowed_roles, "
                    "dp.jwt_validate_exp, dp.jwt_issuer, dp.jwt_audience, dp.jwt_clock_skew_seconds "
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

        policies: Dict[str, Policy] = {}
        for row in policy_rows:
            policy_id, route_id, requires_auth, rate_limit, roles, jwt_exp, iss, aud, skew = row
            policies[route_id] = _policy_from_row(
                policy_id, route_id, requires_auth, rate_limit, roles, jwt_exp, iss, aud, skew
            )

        domain_policies: Dict[str, Policy] = {}
        for row in domain_policy_rows:
            gp_id, domain_host, requires_auth, rate_limit, roles, jwt_exp, iss, aud, skew = row
            domain_policies[domain_host.lower()] = _policy_from_row(
                gp_id, "", requires_auth, rate_limit, roles, jwt_exp, iss, aud, skew
            )

        self._tenant_by_domain = tenant_by_domain
        self._routes = routes
        self._domains = domains
        self._policies = policies
        self._domain_policies = domain_policies

        logger.info(
            "Gateway snapshot: %d domain(s), %d rota(s), %d política(s), %d política(s) de domain.",
            len(self._tenant_by_domain),
            len(self._routes),
            len(self._policies),
            len(self._domain_policies),
        )

    async def reload(self, database_url: str) -> None:
        await self.load(database_url)

    async def get_by_domain(self, host: str) -> Optional[GatewayTenant]:
        clean = host.split(":")[0].lower()
        return self._tenant_by_domain.get(clean)

    async def get_by_path(self, path: str, method: str, tenant_id: str) -> Optional[Route]:
        for route in self._routes:
            if route.tenant_id == tenant_id and route.matches(path, method):
                return route
        return None

    async def list_all(self) -> List[Route]:
        return list(self._routes)

    async def get_by_id(self, domain_id: str) -> Optional[Domain]:
        return self._domains.get(domain_id)

    async def get_by_route_id(self, route_id: str) -> Optional[Policy]:
        return self._policies.get(route_id)

    def get_domain_policy(self, host: str) -> Optional[Policy]:
        clean = host.split(":")[0].lower()
        return self._domain_policies.get(clean)
