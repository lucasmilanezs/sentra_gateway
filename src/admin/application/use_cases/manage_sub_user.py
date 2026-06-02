"""
ManageSubUser

Use case para gerenciamento de sub-usuários dentro de um tenant.

Quem pode usar:
  - superuser: cria/lista/deleta sub-usuários em qualquer tenant
  - admin: cria/lista/deleta sub-usuários apenas no próprio tenant

Regras de negócio:
  - Sub-usuários têm sempre role="member" — admin não pode elevar role
  - Sub-usuário é sempre atrelado ao mesmo tenant do criador (admin)
  - As permissões devem ser um subset das 4 permissões válidas
  - Um member não pode criar outros usuários (enforced no caller level)
"""
import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.password_hasher import PasswordHasherPort
from src.admin.domain.value_objects.permission import Permission
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory


_VALID_PERMISSIONS = {p.value for p in Permission}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_permissions(permissions: list[str]) -> list[str]:
    invalid = [p for p in permissions if p not in _VALID_PERMISSIONS]
    if invalid:
        raise ValidationError(
            f"permissões inválidas: {invalid}. Válidas: {sorted(_VALID_PERMISSIONS)}"
        )
    # Deduplica preservando ordem
    seen: set[str] = set()
    return [p for p in permissions if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]


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
        self._change_audit = change_audit

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
        """
        Cria um sub-usuário (role=member) dentro de um tenant.

        caller_role / caller_tenant_id: extraídos do JWT do requisitante.
        target_tenant_id: só relevante para superuser — admin sempre usa o próprio tenant.
        """
        # Determina tenant alvo
        if caller_role == "superuser":
            tenant_id = (target_tenant_id or "").strip()
            if not tenant_id:
                raise ValidationError("superuser deve informar tenant_id ao criar sub-usuário")
        elif caller_role == "admin":
            if not caller_tenant_id:
                raise AuthError("admin sem tenant vinculado não pode criar sub-usuários")
            if target_tenant_id and target_tenant_id != caller_tenant_id:
                raise AuthError("admin não pode criar sub-usuário em outro tenant")
            tenant_id = caller_tenant_id
        else:
            raise AuthError("apenas admin ou superuser podem criar sub-usuários")

        # Valida tenant
        if not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")

        # Valida e normaliza campos
        if len(password) < 8:
            raise ValidationError("senha deve ter pelo menos 8 caracteres")
        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValidationError("email inválido")
        validated_permissions = _validate_permissions(permissions)
        if not validated_permissions:
            raise ValidationError("sub-usuário deve ter ao menos uma permissão")

        if await self._users.get_by_email(email_n):
            raise ConflictError("email já cadastrado")

        now = _utcnow()
        user = User(
            id=str(uuid.uuid4()),
            email=email_n,
            password_hash=self._hasher.hash(password),
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
            role="member",
            permissions=validated_permissions,
        )
        await self._users.save(user)
        await self._record_change(tenant_id=user.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="CREATE", resource_type="member", resource_id=user.id, resource_summary=user.email, detail={"permissions": user.permissions})
        return user

    async def list_by_tenant(self, *, caller_role: str, caller_tenant_id: str | None, tenant_id: str) -> list[User]:
        """Lista sub-usuários (members) de um tenant."""
        if caller_role == "admin" and caller_tenant_id != tenant_id:
            raise AuthError("acesso negado ao tenant")
        if caller_role not in ("superuser", "admin"):
            raise AuthError("acesso negado")
        return await self._users.list_members_by_tenant(tenant_id)

    async def delete(self, *, caller_role: str, caller_tenant_id: str | None, user_id: str, caller_user_id: str | None = None) -> None:
        """Remove um sub-usuário. Admin só pode remover members do próprio tenant."""
        target = await self._users.get_by_id(user_id)
        if not target:
            raise NotFoundError("usuário não encontrado")
        if target.role != "member":
            raise AuthError("não é permitido remover usuários admin ou superuser por esta rota")
        if caller_role == "admin":
            if target.tenant_id != caller_tenant_id:
                raise AuthError("acesso negado ao tenant")
        elif caller_role != "superuser":
            raise AuthError("acesso negado")
        await self._users.delete(user_id)
        await self._record_change(tenant_id=target.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="DELETE", resource_type="member", resource_id=target.id, resource_summary=target.email, detail={"permissions": target.permissions})

    async def update_permissions(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        user_id: str,
        permissions: list[str],
        caller_user_id: str | None = None,
    ) -> User:
        """Atualiza as permissões de um member existente."""
        target = await self._users.get_by_id(user_id)
        if not target:
            raise NotFoundError("usuário não encontrado")
        if target.role != "member":
            raise AuthError("permissões granulares só se aplicam a members")
        if caller_role == "admin" and target.tenant_id != caller_tenant_id:
            raise AuthError("acesso negado ao tenant")
        elif caller_role not in ("superuser", "admin"):
            raise AuthError("acesso negado")

        validated_permissions = _validate_permissions(permissions)

        updated = User(
            id=target.id,
            email=target.email,
            password_hash=target.password_hash,
            tenant_id=target.tenant_id,
            created_at=target.created_at,
            updated_at=_utcnow(),
            role=target.role,
            permissions=validated_permissions,
        )
        await self._users.save(updated)
        await self._record_change(tenant_id=updated.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role, action="UPDATE", resource_type="member", resource_id=updated.id, resource_summary=updated.email, detail={"permissions": updated.permissions})
        return updated
    async def _record_change(self, *, tenant_id, actor_id, actor_role, action, resource_type, resource_id, resource_summary, detail=None):
        if not self._change_audit:
            return
        await self._change_audit.record(GovernanceAuditEventFactory.build(tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role or "unknown", action=action, resource_type=resource_type, resource_id=resource_id, resource_summary=resource_summary, detail=detail))
