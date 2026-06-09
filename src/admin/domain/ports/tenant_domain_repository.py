from abc import ABC, abstractmethod

from src.admin.domain.entities.tenant_domain import TenantDomain


class TenantDomainRepositoryPort(ABC):
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str) -> list[TenantDomain]:
        ...

    @abstractmethod
    async def get_by_id(self, domain_id: str) -> TenantDomain | None:
        ...

    @abstractmethod
    async def get_by_domain(self, domain: str) -> TenantDomain | None:
        ...

    @abstractmethod
    async def save(self, domain: TenantDomain) -> None:
        ...

    @abstractmethod
    async def delete(self, domain_id: str) -> bool:
        ...
