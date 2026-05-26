from abc import ABC, abstractmethod
from src.admin.domain.entities.admin_change_event import AdminChangeEvent


class ChangeAuditRepositoryPort(ABC):
    @abstractmethod
    async def record(self, event: AdminChangeEvent) -> None: ...

    @abstractmethod
    async def list_for_tenant(self, *, tenant_id: str | None = None, limit: int = 100,
        offset: int = 0, resource_type: str | None = None,
        action: str | None = None) -> tuple[list[AdminChangeEvent], int]: ...
