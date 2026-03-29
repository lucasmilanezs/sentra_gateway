from abc import ABC, abstractmethod

from src.admin.domain.entities.user import User


class UserRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        ...

    @abstractmethod
    async def save(self, user: User) -> None:
        ...
