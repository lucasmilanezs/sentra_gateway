from abc import ABC, abstractmethod

from src.admin.domain.entities.tenant import Tenant


class TenantRepositoryPort(ABC):
    @abstractmethod
    async def list_all(self) -> list[Tenant]:
        ...

    @abstractmethod
    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Tenant | None:
        ...

    @abstractmethod
    async def save(self, tenant: Tenant) -> None:
        ...

    @abstractmethod
    async def delete(self, tenant_id: str) -> bool:
        ...
