from datetime import datetime
from src.admin.domain.ports.audit_repository import AuditRepositoryPort


class QueryAudit:
    def __init__(self, audit_repo: AuditRepositoryPort) -> None:
        self._audit = audit_repo

    async def list_recent(self, *, tenant_id=None, limit=100):
        return await self._audit.list_recent(tenant_id=tenant_id, limit=min(limit, 100))

    async def list_filtered(self, *, tenant_id=None, route_id=None, outcome=None,
                            method=None, path_contains=None, date_from=None, date_to=None, limit=50, offset=0):
        return await self._audit.list_filtered(
            tenant_id=tenant_id, route_id=route_id, outcome=outcome,
            method=method, path_contains=path_contains, date_from=date_from, date_to=date_to,
            limit=min(limit, 200), offset=offset)

    async def metrics_summary(self, *, tenant_id=None, hours=24):
        return await self._audit.metrics_summary(tenant_id=tenant_id, hours=hours)

    async def metrics_by_route(self, *, tenant_id=None, seconds=3600, bucket_seconds=60, date_from=None, date_to=None):
        seconds = max(10, min(int(seconds or 3600), 60 * 60 * 24 * 366))
        bucket_seconds = max(1, min(int(bucket_seconds or 60), seconds))
        return await self._audit.metrics_by_route(
            tenant_id=tenant_id,
            seconds=seconds,
            bucket_seconds=bucket_seconds,
            date_from=date_from,
            date_to=date_to,
        )
