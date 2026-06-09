from abc import ABC, abstractmethod

from src.admin.domain.entities.policy import Policy


class DomainPolicyRepositoryPort(ABC):
    @abstractmethod
    async def get_by_domain_id(self, domain_id: str) -> Policy | None:
        ...

    @abstractmethod
    async def save(self, policy: Policy) -> None:
        ...

    @abstractmethod
    async def delete_by_domain_id(self, domain_id: str) -> bool:
        ...
