from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.tenant_domain import TenantDomain
from src.admin.domain.ports.tenant_domain_repository import TenantDomainRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import TenantDomainORM


def _orm_to_entity(row: TenantDomainORM) -> TenantDomain:
    return TenantDomain(
        id=row.id,
        tenant_id=row.tenant_id,
        domain=row.domain,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(td: TenantDomain) -> TenantDomainORM:
    return TenantDomainORM(
        id=td.id,
        tenant_id=td.tenant_id,
        domain=td.domain,
        created_at=td.created_at,
        updated_at=td.updated_at,
    )


class TenantDomainRepository(TenantDomainRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_tenant(self, tenant_id: str) -> list[TenantDomain]:
        result = await self._session.execute(
            select(TenantDomainORM).where(TenantDomainORM.tenant_id == tenant_id)
        )
        return [_orm_to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, domain_id: str) -> TenantDomain | None:
        row = await self._session.get(TenantDomainORM, domain_id)
        return _orm_to_entity(row) if row else None

    async def get_by_domain(self, domain: str) -> TenantDomain | None:
        result = await self._session.execute(
            select(TenantDomainORM).where(TenantDomainORM.domain == domain)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, td: TenantDomain) -> None:
        existing = await self._session.get(TenantDomainORM, td.id)
        if existing:
            existing.domain = td.domain
            existing.updated_at = td.updated_at
        else:
            self._session.add(_entity_to_orm(td))
        await self._session.flush()

    async def delete(self, domain_id: str) -> bool:
        result = await self._session.execute(
            delete(TenantDomainORM).where(TenantDomainORM.id == domain_id)
        )
        await self._session.flush()
        return result.rowcount > 0
