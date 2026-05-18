from abc import ABC, abstractmethod

from src.admin.domain.entities.audit_request import AuditRequest


class AuditRepositoryPort(ABC):
    @abstractmethod
    async def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditRequest]:
        ...

    @abstractmethod
    async def metrics_summary(
        self,
        *,
        tenant_id: str | None = None,
        hours: int = 24,
    ) -> dict:
        ...
