from abc import ABC, abstractmethod
from typing import Optional

from src.gateway.domain.models.domain import Domain


class DomainRepository(ABC):
    """
    Outbound port for backend domain resolution.

    After route matching, the gateway resolves the corresponding Domain
    to obtain the backend_url used for forwarding.
    Implementations may be in-memory (dev) or database-backed (prod).
    """

    @abstractmethod
    async def get_by_id(self, domain_id: str) -> Optional[Domain]:
        """Returns the Domain with the given id, or None if not found."""
        ...
