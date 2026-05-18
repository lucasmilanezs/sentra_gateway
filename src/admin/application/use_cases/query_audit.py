from src.admin.domain.entities.audit_request import AuditRequest
from src.admin.domain.ports.audit_repository import AuditRepositoryPort


class QueryAudit:
    def __init__(self, audit_repo: AuditRepositoryPort) -> None:
        self._audit = audit_repo

    async def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditRequest]:
        return await self._audit.list_recent(tenant_id=tenant_id, limit=min(limit, 100))

    async def metrics_summary(
        self,
        *,
        tenant_id: str | None = None,
        hours: int = 24,
    ) -> dict:
        return await self._audit.metrics_summary(tenant_id=tenant_id, hours=hours)
