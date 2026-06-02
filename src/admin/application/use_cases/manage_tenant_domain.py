from __future__ import annotations
import uuid
from datetime import datetime, timezone

from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.entities.domain_policy import DomainPolicy
from src.admin.domain.entities.tenant_domain import TenantDomain
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.domain.services.policy_validation import ensure_valid_rate_limit
from src.admin.domain.ports.domain_policy_repository import DomainPolicyRepositoryPort
from src.admin.domain.ports.tenant_domain_repository import TenantDomainRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory


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
        publisher: ConfigNotifier | None = None,
        change_audit: ChangeAuditRepositoryPort | None = None,
    ) -> None:
        self._domains = domains
        self._domain_policies = domain_policies
        self._tenants = tenants
        self._publisher = publisher
        self._change_audit = change_audit

    # ── Domains ────────────────────────────────────────────────────────

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
        caller_user_id: str | None = None,
    ) -> TenantDomain:
        TenantAccessControl.ensure_tenant_access(
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
        await self._record_change(tenant_id=tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="CREATE", resource_type="domain", resource_id=td.id, resource_summary=td.domain, detail={"domain": td.domain})

        if self._publisher:
            await self._publisher.notify_config_updated()

        return td

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        domain_id: str,
        caller_user_id: str | None = None,
    ) -> None:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )
        await self._domains.delete(domain_id)
        await self._record_change(tenant_id=d.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="DELETE", resource_type="domain", resource_id=d.id, resource_summary=d.domain, detail={"domain": d.domain})

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
        TenantAccessControl.ensure_tenant_access(
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
    ) -> DomainPolicy:
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )

        ensure_valid_rate_limit(rate_limit_per_minute)

        existing = await self._domain_policies.get_by_domain_id(domain_id)
        if auth_mode == DomainPolicy.AUTH_JWT_SIGNED and not jwt_signing_key and not (existing and existing.jwt_signing_key_configured):
            raise ValidationError("Validação de assinatura JWT exige uma secret/chave pública configurada.")
        now = _utcnow()

        policy = DomainPolicy(
            id=existing.id if existing else str(uuid.uuid4()),
            domain_id=domain_id,
            requires_auth=bool(requires_auth) if requires_auth is not None else auth_mode != "none",
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
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        await self._domain_policies.save(policy)
        await self._record_change(tenant_id=d.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="UPDATE" if existing else "CREATE", resource_type="domain_policy", resource_id=policy.id, resource_summary=f"domain policy for {d.domain}", detail={"domain_id": domain_id, "auth_mode": policy.auth_mode, "requires_auth": policy.requires_auth, "rate_limit_per_minute": rate_limit_per_minute, "required_headers": required_headers or [], "forbidden_headers": forbidden_headers or [], "required_params": required_params or [], "forbidden_params": forbidden_params or []})

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
        d = await self._domains.get_by_id(domain_id)
        if not d:
            raise NotFoundError("domain não encontrado")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=d.tenant_id,
        )
        deleted = await self._domain_policies.delete_by_domain_id(domain_id)
        if not deleted:
            raise NotFoundError("política não encontrada para este domain")
        await self._record_change(tenant_id=d.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="DELETE", resource_type="domain_policy", resource_id=domain_id, resource_summary=f"domain policy for {d.domain}", detail={"domain_id": domain_id})

        if self._publisher:
            await self._publisher.notify_config_updated()

    async def _record_change(self, *, tenant_id, actor_id, actor_role, action, resource_type, resource_id, resource_summary, detail=None):
        if not self._change_audit:
            return
        await self._change_audit.record(GovernanceAuditEventFactory.build(tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role or "unknown", action=action, resource_type=resource_type, resource_id=resource_id, resource_summary=resource_summary, detail=detail))
