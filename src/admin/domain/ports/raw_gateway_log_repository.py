from __future__ import annotations

from abc import ABC, abstractmethod

from src.admin.domain.entities.raw_gateway_log import RawGatewayLog


class RawGatewayLogRepositoryPort(ABC):
    """Outbound port for short-lived gateway observability logs."""

    @abstractmethod
    async def list_recent(self, *, tenant_id: str | None, limit: int) -> list[RawGatewayLog]:
        ...
