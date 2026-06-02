"""Use case for member users inside a tenant."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.admin.application.services.governance_audit_recorder import GovernanceAuditRecorder
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ConflictError, NotFoundError
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.services.password_hasher import PasswordHasherPort
from src.admin.domain.value_objects.permission import Permission


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManageSubUser:
    def __init__(
        self,
        users: UserRepositoryPort,
        tenants: TenantRepositoryPort,
        hasher: PasswordHasherPort,
        change_audit: ChangeAuditRepositoryPort | None = None,
    ) -> None:
        self._users = users
        self._tenants = tenants
        self._hasher = hasher
        self._audit = GovernanceAuditRecorder(change_audit)

    async def create(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        email: str,
        password: str,
        permissions: list[str],
        target_tenant_id: str | None = None,
        caller_user_id: str | None = None,
    ) -> User:
        tenant_id = TenantAccessControl.resolve_member_target_tenant(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            target_tenant_id=target_tenant_id,
        )
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")

        User.ensure_valid_password(password)
        email_normalized = User.normalize_email(email)
        validated_permissions = Permission.normalize_many(permissions, require_non_empty=True)
        if await self._users.get_by_email(email_normalized):
            raise ConflictError("email já cadastrado")

        now = _utcnow()
        user = User.create_member(
            id=str(uuid.uuid4()),
            email=email_normalized,
            password_hash=self._hasher.hash(password),
            tenant_id=tenant_id,
            permissions=validated_permissions,
            now=now,
        )
        await self._users.save(user)
        await self._audit.record(
            tenant_id=user.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="CREATE",
            resource_type="member",
            resource_id=user.id,
            resource_summary=user.email,
            detail={"permissions": user.permissions},
        )
        return user

    async def list_by_tenant(self, *, caller_role: str, caller_tenant_id: str | None, tenant_id: str) -> list[User]:
        TenantAccessControl.ensure_can_list_members(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            tenant_id=tenant_id,
        )
        return await self._users.list_members_by_tenant(tenant_id)

    async def delete(self, *, caller_role: str, caller_tenant_id: str | None, user_id: str, caller_user_id: str | None = None) -> None:
        target = await self._users.get_by_id(user_id)
        if not target:
            raise NotFoundError("usuário não encontrado")
        TenantAccessControl.ensure_can_modify_member(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            target=target,
        )
        await self._users.delete(user_id)
        await self._audit.record(
            tenant_id=target.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="DELETE",
            resource_type="member",
            resource_id=target.id,
            resource_summary=target.email,
            detail={"permissions": target.permissions},
        )

    async def update_permissions(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        user_id: str,
        permissions: list[str],
        caller_user_id: str | None = None,
    ) -> User:
        target = await self._users.get_by_id(user_id)
        if not target:
            raise NotFoundError("usuário não encontrado")
        TenantAccessControl.ensure_can_modify_member(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            target=target,
        )
        validated_permissions = Permission.normalize_many(permissions)
        updated = target.with_permissions(validated_permissions, now=_utcnow())
        await self._users.save(updated)
        await self._audit.record(
            tenant_id=updated.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="UPDATE",
            resource_type="member",
            resource_id=updated.id,
            resource_summary=updated.email,
            detail={"permissions": updated.permissions},
        )
        return updated
