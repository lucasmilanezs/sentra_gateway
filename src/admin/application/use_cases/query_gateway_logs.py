from __future__ import annotations

from src.admin.domain.entities.raw_gateway_log import RawGatewayLog
from src.admin.domain.ports.raw_gateway_log_repository import RawGatewayLogRepositoryPort


class QueryGatewayLogs:
    """Application use case for reading gateway raw operational logs."""

    def __init__(self, logs: RawGatewayLogRepositoryPort) -> None:
        self._logs = logs

    async def list_recent(self, *, tenant_id: str | None, limit: int = 100) -> list[RawGatewayLog]:
        return await self._logs.list_recent(tenant_id=tenant_id, limit=min(limit, 500))
