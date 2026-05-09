"""
PostgresSnapshotRepository

Carrega rotas e políticas do plano Admin ao startup do Gateway
e as serve a partir de um snapshot em memória.

Design:
  - O Gateway NUNCA escreve no banco — apenas lê.
  - Cada AdminRoute gera um Route + Domain sintético no modelo do Gateway.
  - Políticas são carregadas da tabela admin_policies e indexadas por route_id.
  - O snapshot é recarregado via Redis pub/sub quando o Admin publica
    uma atualização de configuração, sem necessidade de restart.
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
from src.gateway.domain.value_objects.backend_url import BackendUrl
from src.gateway.domain.value_objects.http_method import HttpMethod

logger = logging.getLogger(__name__)


class PostgresSnapshotRepository(RouteRepository, DomainRepository, PolicyRepository):
    """
    Implementação única que satisfaz RouteRepository, DomainRepository e
    PolicyRepository a partir de um snapshot carregado do Postgres.

    Injetada no ForwardRequest como as três portas simultaneamente.
    """

    def __init__(self) -> None:
        self._routes: List[Route] = []
        self._domains: Dict[str, Domain] = {}
        self._policies: Dict[str, Policy] = {}  # route_id → Policy

    async def load(self, database_url: str) -> None:
        """
        Conecta ao Postgres, lê admin_routes + admin_policies e monta
        o snapshot em memória. Chamado no lifespan e pelo reload().
        """
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:
                routes_result = await conn.execute(
                    text(
                        "SELECT id, path_pattern, method, backend_url "
                        "FROM admin_routes "
                        "ORDER BY length(path_pattern) DESC"
                    )
                )
                route_rows = routes_result.fetchall()

                policies_result = await conn.execute(
                    text(
                        "SELECT id, route_id, requires_auth, "
                        "rate_limit_per_minute, allowed_roles "
                        "FROM admin_policies"
                    )
                )
                policy_rows = policies_result.fetchall()
        finally:
            await engine.dispose()

        routes: List[Route] = []
        domains: Dict[str, Domain] = {}
        policies: Dict[str, Policy] = {}

        for row in route_rows:
            route_id, path_pattern, method, backend_url = row
            domain_id = f"domain-{route_id}"

            try:
                http_method = HttpMethod(method.upper())
            except ValueError:
                logger.warning("Rota %s ignorada — método inválido: %s", route_id, method)
                continue

            routes.append(Route(
                id=route_id,
                path_prefix=path_pattern,
                domain_id=domain_id,
                methods=(http_method,),
            ))
            domains[domain_id] = Domain(
                id=domain_id,
                name=f"backend-{route_id}",
                backend_url=BackendUrl(backend_url),
            )

        for row in policy_rows:
            policy_id, route_id, requires_auth, rate_limit_per_minute, allowed_roles = row
            policies[route_id] = Policy(
                id=policy_id,
                route_id=route_id,
                requires_auth=bool(requires_auth),
                rate_limit_per_minute=rate_limit_per_minute,
                allowed_roles=tuple(r for r in allowed_roles.split(",") if r) if allowed_roles else (),
            )

        # Atribuição atômica — requisições em flight usam versão anterior
        # até a próxima iteração do event loop, comportamento correto
        self._routes = routes
        self._domains = domains
        self._policies = policies

        logger.info(
            "Gateway snapshot carregado: %d rota(s), %d política(s) do Postgres.",
            len(self._routes),
            len(self._policies),
        )

    async def reload(self, database_url: str) -> None:
        """
        Recarrega o snapshot em runtime sem derrubar o gateway.
        Chamado pelo subscriber Redis quando o Admin publica uma atualização.
        """
        await self.load(database_url)

    # --- RouteRepository ---

    async def get_by_path(self, path: str, method: str) -> Optional[Route]:
        for route in self._routes:
            if route.matches(path, method):
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