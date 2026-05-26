from abc import ABC, abstractmethod
from datetime import datetime
from src.admin.domain.entities.audit_request import AuditRequest


class AuditRepositoryPort(ABC):
    @abstractmethod
    async def list_recent(self, *, tenant_id: str | None = None, limit: int = 100) -> list[AuditRequest]: ...

    @abstractmethod
    async def list_filtered(self, *, tenant_id: str | None = None, route_id: str | None = None,
        outcome: str | None = None, method: str | None = None,
        path_contains: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
        limit: int = 100, offset: int = 0) -> tuple[list[AuditRequest], int]: ...

    @abstractmethod
    async def metrics_summary(self, *, tenant_id: str | None = None, hours: int = 24) -> dict: ...
