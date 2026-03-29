from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PasswordResetRecord:
    email: str
    code_hash: str
    expires_at: datetime


class PasswordResetRepositoryPort(ABC):
    @abstractmethod
    async def save(self, record: PasswordResetRecord) -> None:
        ...

    @abstractmethod
    async def get_for_email(self, email: str) -> PasswordResetRecord | None:
        ...

    @abstractmethod
    async def clear(self, email: str) -> None:
        ...
