import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.global_policy import GlobalPolicy
from src.admin.domain.exceptions import NotFoundError, ValidationError
from src.admin.domain.services.policy_validation import ensure_valid_rate_limit
from src.admin.domain.ports.global_policy_repository import GlobalPolicyRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.config_notifier import ConfigNotifier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManageGlobalPolicy:
    """
    Use case para gerenciamento de política global por tenant.

    Funciona como fallback para rotas sem Policy individual.
    Semântica upsert: criar ou substituir a política existente do tenant.
    Publica notificação de atualização após cada escrita.
    """

    def __init__(
        self,
        global_policies: GlobalPolicyRepositoryPort,
        tenants: TenantRepositoryPort,
        publisher: ConfigNotifier | None = None,
    ) -> None:
        self._global_policies = global_policies
        self._tenants = tenants
        self._publisher = publisher

    async def get_by_tenant(self, tenant_id: str) -> GlobalPolicy | None:
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        return await self._global_policies.get_by_tenant_id(tenant_id)

    async def upsert(
        self,
        tenant_id: str,
        requires_auth: bool,
        rate_limit_per_minute: int | None,
        allowed_roles: list[str],
    ) -> GlobalPolicy:
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        ensure_valid_rate_limit(rate_limit_per_minute)

        existing = await self._global_policies.get_by_tenant_id(tenant_id)
        now = _utcnow()

        policy = GlobalPolicy(
            id=existing.id if existing else str(uuid.uuid4()),
            tenant_id=tenant_id,
            requires_auth=requires_auth,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )

        await self._global_policies.save(policy)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return policy

    async def delete(self, tenant_id: str) -> None:
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
        deleted = await self._global_policies.delete_by_tenant_id(tenant_id)
        if not deleted:
            raise NotFoundError("política global não encontrada para este tenant")

        if self._publisher:
            await self._publisher.notify_config_updated()
