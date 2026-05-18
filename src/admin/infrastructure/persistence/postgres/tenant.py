from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import TenantORM


def _orm_to_entity(row: TenantORM) -> Tenant:
    return Tenant(
        id=row.id,
        name=row.name,
        alias=row.alias,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(tenant: Tenant) -> TenantORM:
    return TenantORM(
        id=tenant.id,
        name=tenant.name,
        alias=tenant.alias,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


class TenantRepository(TenantRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Tenant]:
        result = await self._session.execute(select(TenantORM))
        return [_orm_to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        result = await self._session.execute(
            select(TenantORM).where(TenantORM.id == tenant_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def get_by_alias(self, alias: str) -> Tenant | None:
        result = await self._session.execute(
            select(TenantORM).where(TenantORM.alias == alias)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, tenant: Tenant) -> None:
        existing = await self._session.get(TenantORM, tenant.id)
        if existing:
            existing.name = tenant.name
            existing.alias = tenant.alias
            existing.updated_at = tenant.updated_at
        else:
            self._session.add(_entity_to_orm(tenant))
        await self._session.flush()

    async def delete(self, tenant_id: str) -> bool:
        result = await self._session.execute(
            delete(TenantORM).where(TenantORM.id == tenant_id)
        )
        await self._session.flush()
        return result.rowcount > 0
