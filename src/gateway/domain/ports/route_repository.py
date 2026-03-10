from abc import ABC, abstractmethod
from typing import Optional

from src.gateway.domain.models.route import Route


class RouteRepository(ABC):
    """
    Contrato para acesso a rotas.
    Domínio e aplicação dependem desta abstração —
    nunca de uma implementação concreta.
    """

    @abstractmethod
    async def get_by_tenant_slug(self, tenant_slug: str) -> Optional[Route]:
        ...