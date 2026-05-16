from abc import ABC, abstractmethod

from src.admin.domain.entities.global_policy import GlobalPolicy


class GlobalPolicyRepositoryPort(ABC):
    @abstractmethod
    async def get_by_tenant_id(self, tenant_id: str) -> GlobalPolicy | None:
        ...

    @abstractmethod
    async def save(self, policy: GlobalPolicy) -> None:
        ...

    @abstractmethod
    async def delete_by_tenant_id(self, tenant_id: str) -> bool:
        ...