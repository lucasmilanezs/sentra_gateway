from abc import ABC, abstractmethod
from typing import List, Optional

from src.gateway.domain.models.route import Route


class RouteRepository(ABC):
    @abstractmethod
    async def get_by_path(self, path: str, method: str, tenant_id: str) -> Optional[Route]:
        """
        Returns the most specific route (longest prefix) matching
        the given path, HTTP method and tenant, or None if no route matches.
        """
        ...

    @abstractmethod
    async def list_all(self) -> List[Route]:
        ...
