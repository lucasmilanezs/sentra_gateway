from abc import ABC, abstractmethod
from datetime import datetime
from src.admin.domain.entities.admin_change_event import AdminChangeEvent


class ChangeAuditRepositoryPort(ABC):
    @abstractmethod
    async def record(self, event: AdminChangeEvent) -> None: ...

    @abstractmethod
    async def list_for_tenant(self, *, tenant_id: str | None = None, limit: int = 100,
        offset: int = 0, resource_type: str | None = None,
        action: str | None = None, actor_role: str | None = None,
        search: str | None = None, date_from: datetime | None = None,
        date_to: datetime | None = None) -> tuple[list[AdminChangeEvent], int]: ...
