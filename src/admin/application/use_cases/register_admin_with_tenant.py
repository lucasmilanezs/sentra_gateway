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
import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ConflictError
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.password_hasher import PasswordHasherPort

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
        # ── Validações de domínio ───────────────────────────────────
        User.ensure_valid_password(password)
        email_n = User.normalize_email(email)
        company_name_n = Tenant.normalize_name(company_name)
        alias_n = Tenant.normalize_alias(company_alias)

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
        tenant = Tenant.create(
            id=str(uuid.uuid4()),
            name=company_name_n,
            alias=alias_n,
            now=now,
        )
        await self._tenants.save(tenant)

        admin = User.create_admin(
            id=str(uuid.uuid4()),
            email=email_n,
            password_hash=self._hasher.hash(password),
            tenant_id=tenant.id,
            now=now,
        )
        await self._users.save(admin)

        return admin, tenant