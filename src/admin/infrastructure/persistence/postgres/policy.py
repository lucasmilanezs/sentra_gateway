from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.policy import Policy
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import PolicyORM
from src.shared.security.secret_cipher import SecretCipher, SecretCipherError, secret_hint


def _csv(lst):
    return ",".join(lst) if lst else ""


def _from_csv(raw):
    return [r for r in (raw or "").split(",") if r]


def _apply_signing_key(row: PolicyORM, policy: Policy, cipher: SecretCipher | None) -> None:
    if policy.auth_mode != Policy.AUTH_JWT_SIGNED:
        row.jwt_signing_algorithm = None
        row.jwt_signing_key_encrypted = None
        row.jwt_signing_key_hint = None
        return
    row.jwt_signing_algorithm = policy.jwt_signing_algorithm or "HS256"
    if policy.jwt_signing_key:
        if not cipher:
            raise SecretCipherError("SENTRA_POLICY_SECRET_KEY is required to store JWT signing material.")
        row.jwt_signing_key_encrypted = cipher.encrypt(policy.jwt_signing_key)
        row.jwt_signing_key_hint = secret_hint(policy.jwt_signing_key)


def _orm_to_entity(row):
    return Policy(
        id=row.id,
        route_id=row.route_id,
        requires_auth=row.requires_auth,
        rate_limit_per_minute=row.rate_limit_per_minute,
        allowed_roles=_from_csv(row.allowed_roles),
        auth_mode=getattr(row, "auth_mode", None),
        jwt_validate_exp=row.jwt_validate_exp,
        jwt_issuer=row.jwt_issuer,
        jwt_audience=row.jwt_audience,
        jwt_clock_skew_seconds=row.jwt_clock_skew_seconds,
        jwt_signing_algorithm=getattr(row, "jwt_signing_algorithm", None),
        jwt_signing_key_configured=bool(getattr(row, "jwt_signing_key_encrypted", None)),
        jwt_signing_key_hint=getattr(row, "jwt_signing_key_hint", None),
        required_headers=_from_csv(row.required_headers),
        forbidden_headers=_from_csv(row.forbidden_headers),
        required_params=_from_csv(row.required_params),
        forbidden_params=_from_csv(row.forbidden_params),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entity_to_orm(p, cipher: SecretCipher | None):
    row = PolicyORM(
        id=p.id,
        route_id=p.route_id,
        requires_auth=p.requires_auth,
        rate_limit_per_minute=p.rate_limit_per_minute,
        allowed_roles=_csv(p.allowed_roles),
        auth_mode=p.auth_mode,
        jwt_validate_exp=p.jwt_validate_exp,
        jwt_issuer=p.jwt_issuer,
        jwt_audience=p.jwt_audience,
        jwt_clock_skew_seconds=p.jwt_clock_skew_seconds,
        jwt_signing_algorithm=p.jwt_signing_algorithm,
        required_headers=_csv(p.required_headers),
        forbidden_headers=_csv(p.forbidden_headers),
        required_params=_csv(p.required_params),
        forbidden_params=_csv(p.forbidden_params),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
    _apply_signing_key(row, p, cipher)
    return row


class PolicyRepository(PolicyRepositoryPort):
    def __init__(self, session: AsyncSession, secret_cipher: SecretCipher | None = None):
        self._session = session
        self._secret_cipher = secret_cipher

    async def get_by_route_id(self, route_id):
        result = await self._session.execute(select(PolicyORM).where(PolicyORM.route_id == route_id))
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def get_by_id(self, policy_id):
        result = await self._session.execute(select(PolicyORM).where(PolicyORM.id == policy_id))
        row = result.scalar_one_or_none()
        return _orm_to_entity(row) if row else None

    async def save(self, policy):
        existing = await self._session.get(PolicyORM, policy.id)
        if existing:
            for attr in (
                "requires_auth",
                "rate_limit_per_minute",
                "auth_mode",
                "jwt_validate_exp",
                "jwt_issuer",
                "jwt_audience",
                "jwt_clock_skew_seconds",
                "jwt_signing_algorithm",
                "updated_at",
            ):
                setattr(existing, attr, getattr(policy, attr))
            for csv_attr in ("allowed_roles","required_headers","forbidden_headers","required_params","forbidden_params"):
                setattr(existing, csv_attr, _csv(getattr(policy, csv_attr)))
            _apply_signing_key(existing, policy, self._secret_cipher)
        else:
            self._session.add(_entity_to_orm(policy, self._secret_cipher))
        await self._session.flush()

    async def delete_by_route_id(self, route_id):
        result = await self._session.execute(delete(PolicyORM).where(PolicyORM.route_id == route_id))
        await self._session.flush()
        return result.rowcount > 0
