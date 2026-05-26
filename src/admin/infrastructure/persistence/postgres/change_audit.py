from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.admin.domain.entities.admin_change_event import AdminChangeEvent
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import AdminChangeAuditORM


def _to_entity(row: AdminChangeAuditORM) -> AdminChangeEvent:
    return AdminChangeEvent(
        id=row.id, tenant_id=row.tenant_id, actor_id=row.actor_id,
        actor_role=row.actor_role, action=row.action, resource_type=row.resource_type,
        resource_id=row.resource_id, resource_summary=row.resource_summary,
        timestamp=row.created_at, detail=row.detail,
    )


class ChangeAuditRepository(ChangeAuditRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AdminChangeEvent) -> None:
        orm = AdminChangeAuditORM(
            id=event.id, tenant_id=event.tenant_id, actor_id=event.actor_id,
            actor_role=event.actor_role, action=event.action, resource_type=event.resource_type,
            resource_id=event.resource_id, resource_summary=event.resource_summary, detail=event.detail,
        )
        self._session.add(orm)
        await self._session.flush()

    async def list_for_tenant(self, *, tenant_id=None, limit=100, offset=0, resource_type=None, action=None):
        q = select(AdminChangeAuditORM)
        count_q = select(func.count(AdminChangeAuditORM.id))
        if tenant_id:
            q = q.where(AdminChangeAuditORM.tenant_id == tenant_id)
            count_q = count_q.where(AdminChangeAuditORM.tenant_id == tenant_id)
        if resource_type:
            q = q.where(AdminChangeAuditORM.resource_type == resource_type)
            count_q = count_q.where(AdminChangeAuditORM.resource_type == resource_type)
        if action:
            q = q.where(AdminChangeAuditORM.action == action)
            count_q = count_q.where(AdminChangeAuditORM.action == action)
        total = (await self._session.execute(count_q)).scalar() or 0
        q = q.order_by(AdminChangeAuditORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(q)
        return [_to_entity(r) for r in result.scalars().all()], total
