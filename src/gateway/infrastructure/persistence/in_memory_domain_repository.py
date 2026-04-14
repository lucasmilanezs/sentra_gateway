from typing import Dict, Optional

from src.gateway.domain.models.domain import Domain
from src.gateway.domain.ports.domain_repository import DomainRepository
from src.gateway.domain.value_objects.backend_url import BackendUrl


_DEFAULT_DOMAINS: Dict[str, Domain] = {
    "domain-httpbin": Domain(
        id="domain-httpbin",
        name="httpbin",
        backend_url=BackendUrl("https://httpbin.org"),
    ),
}


class InMemoryDomainRepository(DomainRepository):
    """
    In-memory domain store for local development and testing.

    Paired with InMemoryRouteRepository: the route "route-httpbin" references
    "domain-httpbin", which resolves to https://httpbin.org.

    Replace with PostgresDomainRepository for production without affecting
    any use case or domain code.
    """

    def __init__(self, domains: Optional[Dict[str, Domain]] = None) -> None:
        self._domains = domains if domains is not None else dict(_DEFAULT_DOMAINS)

    async def get_by_id(self, domain_id: str) -> Optional[Domain]:
        return self._domains.get(domain_id)
