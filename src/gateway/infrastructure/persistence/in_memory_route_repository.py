from typing import Dict, Optional

from src.gateway.domain.models.route import Route
from src.gateway.domain.ports.route_repository import RouteRepository


_ROUTES: Dict[str, Route] = {
    "httpbin": Route(
        tenant_slug="httpbin",
        backend_url="https://httpbin.org",
    ),
}


class InMemoryRouteRepository(RouteRepository):
    """
    Implementação hardcoded do RouteRepository.
    Usada para desenvolvimento e validação do fluxo completo
    antes da persistência real entrar.

    Trocar por PostgresRouteRepository no futuro
    não afeta nenhuma outra camada.
    """

    async def get_by_tenant_slug(self, tenant_slug: str) -> Optional[Route]:
        return _ROUTES.get(tenant_slug)