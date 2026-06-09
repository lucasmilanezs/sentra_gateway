from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.admin.application.services.governance_audit_recorder import GovernanceAuditRecorder
from src.admin.domain.entities.policy import Policy
from src.admin.domain.entities.tenant_domain import TenantDomain
from src.admin.domain.exceptions import ConflictError, NotFoundError
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.admin.domain.ports.domain_policy_repository import DomainPolicyRepositoryPort
from src.admin.domain.ports.tenant_domain_repository import TenantDomainRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.services.access_control import TenantAccessControl


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManageTenantDomain:
    """Use case for tenant domains and their fallback policies."""

    def __init__(
        self,
        domains: TenantDomainRepositoryPort,
        domain_policies: DomainPolicyRepositoryPort,
        tenants: TenantRepositoryPort,
        publisher: ConfigNotifier | None = None,
        change_audit: ChangeAuditRepositoryPort | None = None,
    ) -> None:
        self._domains = domains
        self._domain_policies = domain_policies
        self._tenants = tenants
        self._publisher = publisher
        self._audit = GovernanceAuditRecorder(change_audit)

    async def list(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
    ) -> list[TenantDomain]:
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=tenant_id,
        )
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        return await self._domains.list_by_tenant(tenant_id)

    async def get(self, domain_id: str) -> TenantDomain:
        domain = await self._domains.get_by_id(domain_id)
        if not domain:
            raise NotFoundError("domain não encontrado")
        return domain

    async def create(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        tenant_id: str,
        domain: str,
        caller_user_id: str | None = None,
    ) -> TenantDomain:
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=tenant_id,
        )
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")

        now = _utcnow()
        tenant_domain = TenantDomain.create(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            domain=domain,
            now=now,
        )
        if await self._domains.get_by_domain(tenant_domain.domain):
            raise ConflictError(f"domain '{tenant_domain.domain}' já está em uso")

        await self._domains.save(tenant_domain)
        await self._audit.record(
            tenant_id=tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="CREATE",
            resource_type="domain",
            resource_id=tenant_domain.id,
            resource_summary=tenant_domain.audit_summary(),
            detail=tenant_domain.audit_detail(),
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
        return tenant_domain

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
        caller_user_id: str | None = None,
    ) -> None:
        domain = await self._domains.get_by_id(domain_id)
        if not domain:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=domain.tenant_id,
        )
        await self._domains.delete(domain_id)
        await self._audit.record(
            tenant_id=domain.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="DELETE",
            resource_type="domain",
            resource_id=domain.id,
            resource_summary=domain.audit_summary(),
            detail=domain.audit_detail(),
        )
        if self._publisher:
            await self._publisher.notify_config_updated()

    async def get_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
    ) -> Policy | None:
        domain = await self._domains.get_by_id(domain_id)
        if not domain:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=domain.tenant_id,
        )
        return await self._domain_policies.get_by_domain_id(domain_id)

    async def upsert_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
        auth_mode: str = "none",
        requires_auth: bool | None = None,
        rate_limit_per_minute: int | None = None,
        allowed_roles: list[str] | None = None,
        jwt_validate_exp: bool = True,
        jwt_issuer: str | None = None,
        jwt_audience: str | None = None,
        jwt_clock_skew_seconds: int = 30,
        jwt_signing_algorithm: str | None = None,
        jwt_signing_key: str | None = None,
        required_headers: list[str] | None = None,
        forbidden_headers: list[str] | None = None,
        required_params: list[str] | None = None,
        forbidden_params: list[str] | None = None,
        caller_user_id: str | None = None,
    ) -> Policy:
        domain = await self._domains.get_by_id(domain_id)
        if not domain:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=domain.tenant_id,
        )

        existing = await self._domain_policies.get_by_domain_id(domain_id)
        now = _utcnow()
        data = dict(
            requires_auth=bool(requires_auth) if requires_auth is not None else auth_mode != Policy.AUTH_NONE,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles or [],
            auth_mode=auth_mode,
            jwt_validate_exp=jwt_validate_exp,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            jwt_clock_skew_seconds=jwt_clock_skew_seconds,
            jwt_signing_algorithm=jwt_signing_algorithm,
            jwt_signing_key=jwt_signing_key,
            required_headers=required_headers or [],
            forbidden_headers=forbidden_headers or [],
            required_params=required_params or [],
            forbidden_params=forbidden_params or [],
        )
        policy = (
            existing.reconfigure(now=now, **data)
            if existing
            else Policy.create_for_domain(id=str(uuid.uuid4()), domain_id=domain_id, now=now, **data)
        )
        await self._domain_policies.save(policy)
        await self._audit.record(
            tenant_id=domain.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="UPDATE" if existing else "CREATE",
            resource_type=policy.audit_resource_type(),
            resource_id=policy.id,
            resource_summary=f"domain policy for {domain.domain}",
            detail=policy.audit_detail(),
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
        return policy

    async def delete_policy(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
        caller_user_id: str | None = None,
    ) -> None:
        domain = await self._domains.get_by_id(domain_id)
        if not domain:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=domain.tenant_id,
        )
        deleted = await self._domain_policies.delete_by_domain_id(domain_id)
        if not deleted:
            raise NotFoundError("política não encontrada para este domain")
        await self._audit.record(
            tenant_id=domain.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="DELETE",
            resource_type="domain_policy",
            resource_id=domain_id,
            resource_summary=f"domain policy for {domain.domain}",
            detail={"domain_id": domain_id},
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
