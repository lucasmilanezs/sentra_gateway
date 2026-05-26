"""
PostgresSnapshotRepository — loads admin config into in-memory snapshot.
"""
import logging
from datetime import datetime, timezone
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
        if not m: continue
        try: result.append(HttpMethod(m))
        except ValueError: logger.warning("Método inválido ignorado: %s", m)
    return tuple(result)

def _csv(raw) -> Tuple[str, ...]:
    if not raw: return ()
    return tuple(r for r in str(raw).split(",") if r)

def _policy_from_row(pid, rid, auth, rlimit, roles, jexp, jiss, jaud, jskew,
                     rh=None, fh=None, rp=None, fp=None) -> Policy:
    return Policy(
        id=pid, route_id=rid, requires_auth=bool(auth),
        rate_limit_per_minute=rlimit, allowed_roles=_csv(roles),
        jwt_validate_exp=bool(jexp) if jexp is not None else True,
        jwt_issuer=jiss, jwt_audience=jaud, jwt_clock_skew_seconds=int(jskew or 30),
        required_headers=_csv(rh), forbidden_headers=_csv(fh),
        required_params=_csv(rp), forbidden_params=_csv(fp),
    )

class PostgresSnapshotRepository(RouteRepository, DomainRepository, PolicyRepository, TenantRepository):
    def __init__(self):
        self._routes: List[Route] = []
        self._domains: Dict[str, Domain] = {}
        self._policies: Dict[str, Policy] = {}
        self._domain_policies: Dict[str, Policy] = {}
        self._tenant_by_domain: Dict[str, GatewayTenant] = {}
        self._loaded_at: Optional[datetime] = None

    @property
    def loaded_at(self): return self._loaded_at
    def route_count(self): return len(self._routes)
    def tenant_count(self): return len(self._tenant_by_domain)
    def policy_count(self): return len(self._policies)

    async def load(self, database_url: str) -> None:
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:
                td_rows = (await conn.execute(text(
                    "SELECT td.id, td.tenant_id, td.domain FROM admin_tenant_domains td"))).fetchall()
                rt_rows = (await conn.execute(text(
                    "SELECT id, tenant_id, path_pattern, methods, backend_url FROM admin_routes ORDER BY length(path_pattern) DESC"))).fetchall()
                pol_rows = (await conn.execute(text(
                    "SELECT id, route_id, requires_auth, rate_limit_per_minute, allowed_roles, "
                    "jwt_validate_exp, jwt_issuer, jwt_audience, jwt_clock_skew_seconds, "
                    "required_headers, forbidden_headers, required_params, forbidden_params "
                    "FROM admin_policies"))).fetchall()
                dp_rows = (await conn.execute(text(
                    "SELECT dp.id, td.domain, dp.requires_auth, dp.rate_limit_per_minute, dp.allowed_roles, "
                    "dp.jwt_validate_exp, dp.jwt_issuer, dp.jwt_audience, dp.jwt_clock_skew_seconds, "
                    "dp.required_headers, dp.forbidden_headers, dp.required_params, dp.forbidden_params "
                    "FROM admin_domain_policies dp JOIN admin_tenant_domains td ON td.id = dp.domain_id"))).fetchall()
        finally:
            await engine.dispose()

        tbd: Dict[str, GatewayTenant] = {}
        for row in td_rows:
            did, tid, dom = row
            tbd[dom] = GatewayTenant(id=tid, domain=dom)
        routes, domains = [], {}
        for row in rt_rows:
            rid, tid, pp, mraw, burl = row
            did = f"domain-{rid}"
            routes.append(Route(id=rid, tenant_id=tid, path_prefix=pp, domain_id=did, methods=_parse_methods(mraw)))
            domains[did] = Domain(id=did, name=f"backend-{rid}", backend_url=BackendUrl(burl))
        policies = {}
        for row in pol_rows:
            policies[row[1]] = _policy_from_row(*row)
        dp = {}
        for row in dp_rows:
            dp[row[1].lower()] = _policy_from_row(row[0], "", *row[2:])

        self._tenant_by_domain = tbd
        self._routes = routes
        self._domains = domains
        self._policies = policies
        self._domain_policies = dp
        self._loaded_at = datetime.now(tz=timezone.utc)
        logger.info("Snapshot: %d domain(s), %d rota(s), %d política(s), %d dp(s).",
            len(tbd), len(routes), len(policies), len(dp))

    async def reload(self, database_url): await self.load(database_url)
    async def get_by_domain(self, host):
        return self._tenant_by_domain.get(host.split(":")[0].lower())
    async def get_by_path(self, path, method, tenant_id):
        for r in self._routes:
            if r.tenant_id == tenant_id and r.matches(path, method): return r
        return None
    async def list_all(self): return list(self._routes)
    async def get_by_id(self, domain_id): return self._domains.get(domain_id)
    async def get_by_route_id(self, route_id): return self._policies.get(route_id)
    def get_domain_policy(self, host): return self._domain_policies.get(host.split(":")[0].lower())
