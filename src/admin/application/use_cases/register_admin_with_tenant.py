"""
RegisterAdminWithTenant

Use case de onboarding atômico: cria tenant + admin numa única transação.

Invariantes garantidas:
  - Tenant nasce sempre associado a um admin
  - Admin nasce sempre com tenant_id válido (jamais NULL)
  - Falha em qualquer etapa não deixa dados órfãos (rollback transacional)

Esta é a ÚNICA forma pública de criar admin via fluxo de cadastro.
RegisterUser (criação isolada com tenant_id opcional) foi deprecado para
evitar a criação de admins órfãos sem tenant.

Apenas o superuser, criado via bootstrap em deploy, possui tenant_id=NULL.
"""
import re
import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ConflictError, ValidationError
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.password_hasher import PasswordHasherPort

_ALIAS_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RegisterAdminWithTenant:
    def __init__(
        self,
        users: UserRepositoryPort,
        tenants: TenantRepositoryPort,
        hasher: PasswordHasherPort,
    ) -> None:
        self._users = users
        self._tenants = tenants
        self._hasher = hasher

    async def execute(
        self,
        email: str,
        password: str,
        company_name: str,
        company_alias: str,
    ) -> tuple[User, Tenant]:
        # ── Validações ──────────────────────────────────────────────
        if len(password) < 8:
            raise ValidationError("senha deve ter pelo menos 8 caracteres")

        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValidationError("email inválido")

        company_name_n = company_name.strip()
        if not company_name_n or len(company_name_n) > 255:
            raise ValidationError("nome da empresa inválido")

        alias_n = company_alias.strip().lower()
        if not alias_n or len(alias_n) > 128:
            raise ValidationError("alias da empresa inválido")
        if not _ALIAS_RE.match(alias_n):
            raise ValidationError(
                "alias deve conter apenas letras minúsculas, números e hífens"
            )

        # ── Checagens de unicidade ──────────────────────────────────
        if await self._users.get_by_email(email_n):
            raise ConflictError("email já cadastrado")
        if await self._tenants.get_by_alias(alias_n):
            raise ConflictError("alias já em uso")

        now = _utcnow()

        # ── Criação atômica ─────────────────────────────────────────
        # Ambos os save() compartilham a mesma session via wiring por request.
        # Como o request inteiro é envolto em session.begin(), se qualquer
        # save() levantar exceção, o transaction manager faz rollback de tudo.
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=company_name_n,
            alias=alias_n,
            created_at=now,
            updated_at=now,
        )
        await self._tenants.save(tenant)

        admin = User(
            id=str(uuid.uuid4()),
            email=email_n,
            password_hash=self._hasher.hash(password),
            tenant_id=tenant.id,  # invariante: admin SEMPRE tem tenant_id
            created_at=now,
            updated_at=now,
            role="admin",
            permissions=[],  # admin tem acesso total implícito, sem permissions granulares
        )
        await self._users.save(admin)

        return admin, tenant