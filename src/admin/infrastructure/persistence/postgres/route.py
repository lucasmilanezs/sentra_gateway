from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.value_objects.http_method import HttpMethod
from src.admin.infrastructure.persistence.postgres.models import AdminRouteORM


def _orm_to_entity(row: AdminRouteORM) -> AdminRoute:
    return AdminRoute(
        id=row.id,
        tenant_id=row.tenant_id,
        path_pattern=row.path_pattern,
        method=HttpMethod(row.method),
        backend_url=row.backend_url,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(route: AdminRoute) -> AdminRouteORM:
    return AdminRouteORM(
        id=route.id,
        tenant_id=route.tenant_id,
        path_pattern=route.path_pattern,
        method=route.method.value,
        backend_url=route.backend_url,
        created_at=route.created_at,
        updated_at=route.updated_at,
    )


class RouteRepository(AdminRouteRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, tenant_id: str | None = None) -> list[AdminRoute]:
        stmt = select(AdminRouteORM)
        if tenant_id is not None:
            stmt = stmt.where(AdminRouteORM.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return [_orm_to_entity(row) for row in result.scalars().all()]

    async def get_by_id(self, route_id: str) -> AdminRoute | None:
        result = await self._session.execute(
            select(AdminRouteORM).where(AdminRouteORM.id == route_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, route: AdminRoute) -> None:
        existing = await self._session.get(AdminRouteORM, route.id)
        if existing:
            existing.tenant_id = route.tenant_id
            existing.path_pattern = route.path_pattern
            existing.method = route.method.value
            existing.backend_url = route.backend_url
            existing.updated_at = route.updated_at
        else:
            self._session.add(_entity_to_orm(route))
        await self._session.flush()

    async def delete(self, route_id: str) -> bool:
        result = await self._session.execute(
            delete(AdminRouteORM).where(AdminRouteORM.id == route_id)
        )
        await self._session.flush()
        return result.rowcount > 0