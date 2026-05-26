from __future__ import annotations
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.domain_policy import DomainPolicy
from src.admin.domain.ports.domain_policy_repository import DomainPolicyRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import DomainPolicyORM


def _csv(values: list[str] | None) -> str:
    return ",".join(values or [])


def _from_csv(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _orm_to_entity(row: DomainPolicyORM) -> DomainPolicy:
    return DomainPolicy(
        id=row.id,
        domain_id=row.domain_id,
        requires_auth=row.requires_auth,
        rate_limit_per_minute=row.rate_limit_per_minute,
        allowed_roles=_from_csv(row.allowed_roles),
        jwt_validate_exp=row.jwt_validate_exp,
        jwt_issuer=row.jwt_issuer,
        jwt_audience=row.jwt_audience,
        jwt_clock_skew_seconds=row.jwt_clock_skew_seconds,
        required_headers=_from_csv(row.required_headers),
        forbidden_headers=_from_csv(row.forbidden_headers),
        required_params=_from_csv(row.required_params),
        forbidden_params=_from_csv(row.forbidden_params),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(policy: DomainPolicy) -> DomainPolicyORM:
    return DomainPolicyORM(
        id=policy.id,
        domain_id=policy.domain_id,
        requires_auth=policy.requires_auth,
        rate_limit_per_minute=policy.rate_limit_per_minute,
        allowed_roles=_csv(policy.allowed_roles),
        jwt_validate_exp=policy.jwt_validate_exp,
        jwt_issuer=policy.jwt_issuer,
        jwt_audience=policy.jwt_audience,
        jwt_clock_skew_seconds=policy.jwt_clock_skew_seconds,
        required_headers=_csv(policy.required_headers),
        forbidden_headers=_csv(policy.forbidden_headers),
        required_params=_csv(policy.required_params),
        forbidden_params=_csv(policy.forbidden_params),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


class DomainPolicyRepository(DomainPolicyRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_domain_id(self, domain_id: str) -> DomainPolicy | None:
        result = await self._session.execute(
            select(DomainPolicyORM).where(DomainPolicyORM.domain_id == domain_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, policy: DomainPolicy) -> None:
        existing = await self._session.get(DomainPolicyORM, policy.id)
        if existing:
            existing.requires_auth = policy.requires_auth
            existing.rate_limit_per_minute = policy.rate_limit_per_minute
            existing.allowed_roles = _csv(policy.allowed_roles)
            existing.jwt_validate_exp = policy.jwt_validate_exp
            existing.jwt_issuer = policy.jwt_issuer
            existing.jwt_audience = policy.jwt_audience
            existing.jwt_clock_skew_seconds = policy.jwt_clock_skew_seconds
            existing.required_headers = _csv(policy.required_headers)
            existing.forbidden_headers = _csv(policy.forbidden_headers)
            existing.required_params = _csv(policy.required_params)
            existing.forbidden_params = _csv(policy.forbidden_params)
            existing.updated_at = policy.updated_at
        else:
            self._session.add(_entity_to_orm(policy))
        await self._session.flush()

    async def delete_by_domain_id(self, domain_id: str) -> bool:
        result = await self._session.execute(
            delete(DomainPolicyORM).where(DomainPolicyORM.domain_id == domain_id)
        )
        await self._session.flush()
        return result.rowcount > 0
