from abc import ABC, abstractmethod

from src.admin.domain.entities.user import User


class UserRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def list_members_by_tenant(self, tenant_id: str) -> list[User]: ...

    @abstractmethod
    async def delete(self, user_id: str) -> bool: ...