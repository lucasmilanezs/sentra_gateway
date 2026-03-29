from abc import ABC, abstractmethod

from src.admin.domain.entities.admin_route import AdminRoute


class AdminRouteRepositoryPort(ABC):
    @abstractmethod
    async def list_all(self, tenant_id: str | None = None) -> list[AdminRoute]:
        ...

    @abstractmethod
    async def get_by_id(self, route_id: str) -> AdminRoute | None:
        ...

    @abstractmethod
    async def save(self, route: AdminRoute) -> None:
        ...

    @abstractmethod
    async def delete(self, route_id: str) -> bool:
        ...
