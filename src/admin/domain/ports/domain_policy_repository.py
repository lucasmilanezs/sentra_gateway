from abc import ABC, abstractmethod

from src.admin.domain.entities.domain_policy import DomainPolicy


class DomainPolicyRepositoryPort(ABC):
    @abstractmethod
    async def get_by_domain_id(self, domain_id: str) -> DomainPolicy | None:
        ...

    @abstractmethod
    async def save(self, policy: DomainPolicy) -> None:
        ...

    @abstractmethod
    async def delete_by_domain_id(self, domain_id: str) -> bool:
        ...
