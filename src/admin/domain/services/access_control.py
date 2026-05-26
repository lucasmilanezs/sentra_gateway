from __future__ import annotations

from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import AuthError, ValidationError


class TenantAccessControl:
    """Domain service that enforces tenant isolation and admin/member boundaries."""

    @staticmethod
    def is_superuser(role: str | None) -> bool:
        return role == "superuser"

    @staticmethod
    def is_admin(role: str | None) -> bool:
        return role == "admin"

    @classmethod
    def is_admin_like(cls, role: str | None) -> bool:
        return cls.is_superuser(role) or cls.is_admin(role)

    @staticmethod
    def ensure_tenant_access(
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        resource_tenant_id: str,
    ) -> None:
        if caller_role == "superuser":
            return
        if caller_tenant_id != resource_tenant_id:
            raise AuthError("acesso negado ao tenant")

    @staticmethod
    def resolve_read_scope(
        *, caller_role: str | None, caller_tenant_id: str | None, requested_tenant_id: str | None
    ) -> str | None:
        if caller_role == "superuser":
            return requested_tenant_id
        return caller_tenant_id

    @classmethod
    def resolve_member_target_tenant(
        cls,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        target_tenant_id: str | None,
    ) -> str:
        if caller_role == "superuser":
            if not target_tenant_id:
                raise ValidationError("superuser deve informar tenant_id ao criar sub-usuário")
            return target_tenant_id
        if caller_role == "admin":
            if not caller_tenant_id:
                raise AuthError("admin sem tenant vinculado não pode criar sub-usuários")
            return caller_tenant_id
        raise AuthError("apenas admin ou superuser podem criar sub-usuários")

    @classmethod
    def ensure_can_list_members(
        cls, *, caller_role: str, caller_tenant_id: str | None, tenant_id: str
    ) -> None:
        if caller_role not in ("superuser", "admin"):
            raise AuthError("acesso negado")
        cls.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=tenant_id,
        )

    @classmethod
    def ensure_can_modify_member(
        cls, *, caller_role: str, caller_tenant_id: str | None, target: User
    ) -> None:
        if target.role != "member":
            raise AuthError("não é permitido modificar usuários admin ou superuser por esta rota")
        if caller_role not in ("superuser", "admin"):
            raise AuthError("acesso negado")
        if target.tenant_id is None:
            raise AuthError("member sem tenant vinculado não pode ser modificado")
        cls.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=target.tenant_id,
        )

    # Compatibility alias for the older guard naming used by existing use cases.
    assert_access = ensure_tenant_access
