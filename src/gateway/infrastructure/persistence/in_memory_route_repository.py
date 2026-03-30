from typing import List, Optional

from src.gateway.domain.models.route import Route
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.domain.value_objects.http_method import HttpMethod


_DEFAULT_ROUTES: List[Route] = [
    Route(
        id="route-httpbin",
        path_prefix="/httpbin",
        domain_id="domain-httpbin",
        methods=(HttpMethod.GET, HttpMethod.POST),
    ),
]


class InMemoryRouteRepository(RouteRepository):
    """
    In-memory route store for local development and testing.

    Routes are sorted by path_prefix length descending at construction time,
    implementing longest-prefix-match semantics: the most specific route
    (longest prefix) wins when multiple routes could match the same path.

    Replace with a database-backed or cache-backed implementation for
    production without modifying any use case or domain code.
    """

    def __init__(self, routes: Optional[List[Route]] = None) -> None:
        source = routes if routes is not None else _DEFAULT_ROUTES
        self._routes: List[Route] = sorted(
            source,
            key=lambda r: len(r.path_prefix),
            reverse=True,
        )

    async def get_by_path(self, path: str, method: str) -> Optional[Route]:
        for route in self._routes:
            if route.matches(path, method):
                return route
        return None

    async def list_all(self) -> List[Route]:
        return list(self._routes)
