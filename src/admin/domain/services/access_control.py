from __future__ import annotations

from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import AuthError, ValidationError
from src.admin.domain.value_objects.jwt_claims import JwtClaims


class TenantAccessControl:
    """Domain service that enforces tenant isolation, RBAC and admin/member boundaries."""

    @staticmethod
    def is_superuser(role: str | None) -> bool:
        return role == "superuser"

    @staticmethod
    def is_admin(role: str | None) -> bool:
        return role == "admin"

    @classmethod
    def is_admin_like(cls, role: str | None) -> bool:
        return cls.is_superuser(role) or cls.is_admin(role)

    @classmethod
    def ensure_has_permission(cls, claims: JwtClaims, permission: str) -> None:
        if not claims.has_permission(permission):
            raise AuthError(f"permissão '{permission}' necessária")

    @classmethod
    def ensure_admin_like_claims(cls, claims: JwtClaims) -> None:
        if not claims.is_admin_like():
            raise AuthError("acesso restrito a administradores")

    @classmethod
    def ensure_superuser_claims(cls, claims: JwtClaims) -> None:
        if not claims.is_superuser():
            raise AuthError("acesso restrito ao superuser")

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

    @staticmethod
    def resolve_write_scope(
        *, caller_role: str | None, caller_tenant_id: str | None, requested_tenant_id: str | None
    ) -> str:
        if caller_role == "superuser":
            if not requested_tenant_id:
                raise ValidationError("tenant_id é obrigatório para superuser")
            return requested_tenant_id
        if not caller_tenant_id:
            raise AuthError("caller sem tenant vinculado não pode executar esta ação")
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
            if target_tenant_id and target_tenant_id != caller_tenant_id:
                raise AuthError("admin não pode criar sub-usuário em outro tenant")
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
