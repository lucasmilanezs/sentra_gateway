from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.admin.domain.entities.admin_change_event import AdminChangeEvent
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import AdminChangeAuditORM, TenantORM, UserORM


def _to_entity(row) -> AdminChangeEvent:
    audit = row[0]
    tenant = row[1]
    actor = row[2]
    tenant_label = tenant.name if tenant else None
    actor_label = actor.email if actor else f"{audit.actor_role}"
    return AdminChangeEvent(
        id=audit.id, tenant_id=audit.tenant_id, actor_id=audit.actor_id,
        actor_role=audit.actor_role, action=audit.action, resource_type=audit.resource_type,
        resource_id=audit.resource_id, resource_summary=audit.resource_summary,
        timestamp=audit.created_at, detail=audit.detail, tenant_label=tenant_label,
        actor_label=actor_label, resource_label=audit.resource_summary,
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

    async def list_for_tenant(self, *, tenant_id=None, limit=100, offset=0, resource_type=None, action=None, actor_role=None, search=None, date_from=None, date_to=None):
        q = (
            select(AdminChangeAuditORM, TenantORM, UserORM)
            .outerjoin(TenantORM, AdminChangeAuditORM.tenant_id == TenantORM.id)
            .outerjoin(UserORM, AdminChangeAuditORM.actor_id == UserORM.id)
        )
        count_q = (select(func.count(AdminChangeAuditORM.id))
            .outerjoin(UserORM, AdminChangeAuditORM.actor_id == UserORM.id))
        filters = []
        if tenant_id: filters.append(AdminChangeAuditORM.tenant_id == tenant_id)
        if resource_type: filters.append(AdminChangeAuditORM.resource_type == resource_type)
        if action: filters.append(AdminChangeAuditORM.action == action)
        if actor_role: filters.append(AdminChangeAuditORM.actor_role == actor_role)
        if date_from: filters.append(AdminChangeAuditORM.created_at >= date_from)
        if date_to: filters.append(AdminChangeAuditORM.created_at <= date_to)
        if search:
            like = f"%{search}%"
            filters.append(or_(
                AdminChangeAuditORM.resource_summary.ilike(like),
                AdminChangeAuditORM.detail.ilike(like),
                AdminChangeAuditORM.action.ilike(like),
                AdminChangeAuditORM.resource_type.ilike(like),
                UserORM.email.ilike(like),
            ))
        for f in filters:
            q = q.where(f)
            count_q = count_q.where(f)
        total = (await self._session.execute(count_q)).scalar() or 0
        q = q.order_by(AdminChangeAuditORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(q)
        return [_to_entity(r) for r in result.all()], total
