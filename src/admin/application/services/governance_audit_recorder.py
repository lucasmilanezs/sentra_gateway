from __future__ import annotations

from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory


class GovernanceAuditRecorder:
    """Application service that persists configuration-change audit events."""

    def __init__(self, repository: ChangeAuditRepositoryPort | None) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        tenant_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_summary: str,
        detail: dict | None = None,
    ) -> None:
        if not self._repository:
            return
        event = GovernanceAuditEventFactory.build(
            tenant_id=tenant_id,
            actor_id=actor_id or "unknown",
            actor_role=actor_role or "unknown",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_summary=resource_summary,
            detail=detail,
        )
        await self._repository.record(event)
