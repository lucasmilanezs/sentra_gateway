from abc import ABC, abstractmethod

from src.admin.domain.entities.policy import Policy


class PolicyRepositoryPort(ABC):
    @abstractmethod
    async def get_by_route_id(self, route_id: str) -> Policy | None:
        ...

    @abstractmethod
    async def get_by_id(self, policy_id: str) -> Policy | None:
        ...

    @abstractmethod
    async def save(self, policy: Policy) -> None:
        ...

    @abstractmethod
    async def delete_by_route_id(self, route_id: str) -> bool:
        ...