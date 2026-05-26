from abc import ABC, abstractmethod
from src.gateway.domain.models.audit_event import AuditEvent


class AuditPort(ABC):
    @abstractmethod
    async def write(self, event: AuditEvent) -> None: ...
