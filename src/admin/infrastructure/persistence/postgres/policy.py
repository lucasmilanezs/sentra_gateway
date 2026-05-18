from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.policy import Policy
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import PolicyORM


def _orm_to_entity(row: PolicyORM) -> Policy:
    return Policy(
        id=row.id,
        route_id=row.route_id,
        requires_auth=row.requires_auth,
        rate_limit_per_minute=row.rate_limit_per_minute,
        allowed_roles=[r for r in row.allowed_roles.split(",") if r] if row.allowed_roles else [],
        jwt_validate_exp=row.jwt_validate_exp,
        jwt_issuer=row.jwt_issuer,
        jwt_audience=row.jwt_audience,
        jwt_clock_skew_seconds=row.jwt_clock_skew_seconds,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(policy: Policy) -> PolicyORM:
    return PolicyORM(
        id=policy.id,
        route_id=policy.route_id,
        requires_auth=policy.requires_auth,
        rate_limit_per_minute=policy.rate_limit_per_minute,
        allowed_roles=",".join(policy.allowed_roles),
        jwt_validate_exp=policy.jwt_validate_exp,
        jwt_issuer=policy.jwt_issuer,
        jwt_audience=policy.jwt_audience,
        jwt_clock_skew_seconds=policy.jwt_clock_skew_seconds,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


class PolicyRepository(PolicyRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_route_id(self, route_id: str) -> Policy | None:
        result = await self._session.execute(
            select(PolicyORM).where(PolicyORM.route_id == route_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def get_by_id(self, policy_id: str) -> Policy | None:
        result = await self._session.execute(
            select(PolicyORM).where(PolicyORM.id == policy_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, policy: Policy) -> None:
        existing = await self._session.get(PolicyORM, policy.id)
        if existing:
            existing.requires_auth = policy.requires_auth
            existing.rate_limit_per_minute = policy.rate_limit_per_minute
            existing.allowed_roles = ",".join(policy.allowed_roles)
            existing.jwt_validate_exp = policy.jwt_validate_exp
            existing.jwt_issuer = policy.jwt_issuer
            existing.jwt_audience = policy.jwt_audience
            existing.jwt_clock_skew_seconds = policy.jwt_clock_skew_seconds
            existing.updated_at = policy.updated_at
        else:
            self._session.add(_entity_to_orm(policy))
        await self._session.flush()

    async def delete_by_route_id(self, route_id: str) -> bool:
        result = await self._session.execute(
            delete(PolicyORM).where(PolicyORM.route_id == route_id)
        )
        await self._session.flush()
        return result.rowcount > 0
