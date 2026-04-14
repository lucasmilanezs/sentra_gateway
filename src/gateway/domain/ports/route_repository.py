from abc import ABC, abstractmethod
from typing import List, Optional

from src.gateway.domain.models.route import Route


class RouteRepository(ABC):
    """
    Outbound port for route resolution.

    The gateway reads routes to match incoming requests against registered
    path prefixes. Implementations may use in-memory stores, PostgreSQL,
    or a cached snapshot — the use case is oblivious to the backing store.
    """

    @abstractmethod
    async def get_by_path(self, path: str, method: str) -> Optional[Route]:
        """
        Returns the most specific route (longest prefix) matching
        the given path and HTTP method, or None if no route matches.
        """
        ...

    @abstractmethod
    async def list_all(self) -> List[Route]:
        """Returns all registered routes."""
        ...
