"""
PostgresSnapshotRepository

Carrega todas as rotas registradas no plano Admin ao startup do Gateway
e as serve a partir de um snapshot em memória.

Design:
  - O Gateway NUNCA escreve no banco — apenas lê ao inicializar.
  - Cada AdminRoute gera um Route (domínio do Gateway) + um Domain sintético.
    O Admin armazena backend_url diretamente na rota, então o Gateway sintetiza
    um Domain com id = "domain-{route_id}" para honrar a separação de modelos.
  - Sem refresh automático por enquanto — o container reinicia quando as rotas
    mudam. Redis pub/sub entrará em seguida.
  - PolicyRepository retorna None para todas as rotas (open by default),
    até que o plano Admin exponha políticas.
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

    Injetada no ForwardRequest como as três portas ao mesmo tempo.
    """

    def __init__(self) -> None:
        # Sorted by path_prefix length desc — longest-prefix match
        self._routes: List[Route] = []
        self._domains: Dict[str, Domain] = {}

    async def load(self, database_url: str) -> None:
        """
        Conecta ao Postgres, lê admin_routes e monta o snapshot em memória.
        Chamado uma única vez no lifespan do Gateway.
        """
        engine = create_async_engine(database_url, echo=False)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT id, path_pattern, method, backend_url "
                        "FROM admin_routes "
                        "ORDER BY length(path_pattern) DESC"
                    )
                )
                rows = result.fetchall()
        finally:
            await engine.dispose()

        routes: List[Route] = []
        domains: Dict[str, Domain] = {}

        for row in rows:
            route_id, path_pattern, method, backend_url = row

            domain_id = f"domain-{route_id}"

            try:
                http_method = HttpMethod(method.upper())
            except ValueError:
                logger.warning("Rota %s ignorada — método inválido: %s", route_id, method)
                continue

            route = Route(
                id=route_id,
                path_prefix=path_pattern,
                domain_id=domain_id,
                methods=(http_method,),
            )
            domain = Domain(
                id=domain_id,
                name=f"backend-{route_id}",
                backend_url=BackendUrl(backend_url),
            )
            routes.append(route)
            domains[domain_id] = domain

        self._routes = routes
        self._domains = domains

        logger.info(
            "Gateway snapshot carregado: %d rota(s) do Postgres.", len(self._routes)
        )

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
        # Sem políticas configuradas ainda — open by default.
        # Quando o Admin expor políticas, este método as carregará no snapshot.
        return None