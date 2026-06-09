from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.user import User
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import UserORM


def _orm_to_entity(row: UserORM) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        tenant_id=row.tenant_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        role=row.role,
        permissions=[p for p in row.permissions.split(",") if p] if row.permissions else [],
    )


def _entity_to_orm(user: User) -> UserORM:
    return UserORM(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        tenant_id=user.tenant_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        role=user.role,
        permissions=",".join(user.permissions),
    )


class UserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, user: User) -> None:
        existing = await self._session.get(UserORM, user.id)
        if existing:
            existing.email = user.email
            existing.password_hash = user.password_hash
            existing.tenant_id = user.tenant_id
            existing.role = user.role
            existing.permissions = ",".join(user.permissions)
            existing.updated_at = user.updated_at
        else:
            self._session.add(_entity_to_orm(user))
        await self._session.flush()

    async def list_members_by_tenant(self, tenant_id: str) -> list[User]:
        result = await self._session.execute(
            select(UserORM).where(
                UserORM.tenant_id == tenant_id,
                UserORM.role == "member",
            )
        )
        return [_orm_to_entity(row) for row in result.scalars().all()]

    async def delete(self, user_id: str) -> bool:
        result = await self._session.execute(
            delete(UserORM).where(UserORM.id == user_id)
        )
        await self._session.flush()
        return result.rowcount > 0