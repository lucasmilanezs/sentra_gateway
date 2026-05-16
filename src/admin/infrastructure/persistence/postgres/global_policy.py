from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.global_policy import GlobalPolicy
from src.admin.domain.ports.global_policy_repository import GlobalPolicyRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import GlobalPolicyORM


def _orm_to_entity(row: GlobalPolicyORM) -> GlobalPolicy:
    return GlobalPolicy(
        id=row.id,
        tenant_id=row.tenant_id,
        requires_auth=row.requires_auth,
        rate_limit_per_minute=row.rate_limit_per_minute,
        allowed_roles=[r for r in row.allowed_roles.split(",") if r] if row.allowed_roles else [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(policy: GlobalPolicy) -> GlobalPolicyORM:
    return GlobalPolicyORM(
        id=policy.id,
        tenant_id=policy.tenant_id,
        requires_auth=policy.requires_auth,
        rate_limit_per_minute=policy.rate_limit_per_minute,
        allowed_roles=",".join(policy.allowed_roles),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


class GlobalPolicyRepository(GlobalPolicyRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_tenant_id(self, tenant_id: str) -> GlobalPolicy | None:
        result = await self._session.execute(
            select(GlobalPolicyORM).where(GlobalPolicyORM.tenant_id == tenant_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, policy: GlobalPolicy) -> None:
        existing = await self._session.get(GlobalPolicyORM, policy.id)
        if existing:
            existing.requires_auth = policy.requires_auth
            existing.rate_limit_per_minute = policy.rate_limit_per_minute
            existing.allowed_roles = ",".join(policy.allowed_roles)
            existing.updated_at = policy.updated_at
        else:
            self._session.add(_entity_to_orm(policy))
        await self._session.flush()

    async def delete_by_tenant_id(self, tenant_id: str) -> bool:
        result = await self._session.execute(
            delete(GlobalPolicyORM).where(GlobalPolicyORM.tenant_id == tenant_id)
        )
        await self._session.flush()
        return result.rowcount > 0