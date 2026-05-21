from __future__ import annotations
import uuid
from datetime import datetime, timezone

from src.admin.application.services.tenant_ownership_guard import TenantOwnershipGuard
from src.admin.domain.entities.domain_policy import DomainPolicy
from src.admin.domain.entities.tenant_domain import TenantDomain
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.domain.ports.domain_policy_repository import DomainPolicyRepositoryPort
from src.admin.domain.ports.tenant_domain_repository import TenantDomainRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.infrastructure.pubsub.redis_publisher import RedisPublisher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManageTenantDomain:
    """
    Use case para gerenciamento de domains vinculados a um tenant.

    Um tenant pode ter múltiplos domains/subdomains. O gateway usa o
    Host header para resolver qual tenant está sendo acessado.

    Cada domain pode ter uma DomainPolicy (política global fallback):
    aplicada a rotas do tenant que não possuam Policy individual.
    """

    def __init__(
        self,
        domains: TenantDomainRepositoryPort,
        domain_policies: DomainPolicyRepositoryPort,
        tenants: TenantRepositoryPort,
        publisher: RedisPublisher | None = None,
    ) -> None:
        self._domains = domains
        self._domain_policies = domain_policies
        self._tenants = tenants
        self._publisher = publisher

    # ── Domains ────────────────────────────────────────────────────────

    async def list(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
    ) -> list[TenantDomain]:
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=tenant_id,
        )
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        return await self._domains.list_by_tenant(tenant_id)

    async def get(self, domain_id: str) -> TenantDomain:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        return d

    async def create(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
        domain: str,
    ) -> TenantDomain:
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=tenant_id,
        )
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")

        domain = domain.strip().lower()
        if not domain:
            raise ValidationError("domain não pode ser vazio")

        # Garante unicidade global de domain
        existing = await self._domains.get_by_domain(domain)
        if existing:
            raise ConflictError(f"domain '{domain}' já está em uso")

        now = _utcnow()
        td = TenantDomain(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            domain=domain,
            created_at=now,
            updated_at=now,
        )
        await self._domains.save(td)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return td

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
    ) -> None:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )
        await self._domains.delete(domain_id)

        if self._publisher:
            await self._publisher.notify_config_updated()

    # ── Domain Policy (política global por domain) ─────────────────────

    async def get_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
    ) -> DomainPolicy | None:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )
        return await self._domain_policies.get_by_domain_id(domain_id)

    async def upsert_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
        requires_auth: bool,
        rate_limit_per_minute: int | None,
        allowed_roles: list[str],
        jwt_validate_exp: bool = True,
        jwt_issuer: str | None = None,
        jwt_audience: str | None = None,
        jwt_clock_skew_seconds: int = 30,
    ) -> DomainPolicy:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )

        if rate_limit_per_minute is not None and rate_limit_per_minute <= 0:
            raise ValidationError("rate_limit_per_minute deve ser maior que zero")

        existing = await self._domain_policies.get_by_domain_id(domain_id)
        now = _utcnow()

        policy = DomainPolicy(
            id=existing.id if existing else str(uuid.uuid4()),
            domain_id=domain_id,
            requires_auth=requires_auth,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles,
            jwt_validate_exp=jwt_validate_exp,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            jwt_clock_skew_seconds=jwt_clock_skew_seconds,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        await self._domain_policies.save(policy)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return policy

    async def delete_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
    ) -> None:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )
        deleted = await self._domain_policies.delete_by_domain_id(domain_id)
        if not deleted:
            raise NotFoundError("política não encontrada para este domain")

        if self._publisher:
            await self._publisher.notify_config_updated()
