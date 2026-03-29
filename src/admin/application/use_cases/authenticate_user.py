import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.domain.ports.email_sender import EmailSenderPort
from src.admin.domain.ports.password_reset_repository import PasswordResetRecord, PasswordResetRepositoryPort
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.password_hasher import PasswordHasherPort
from src.admin.domain.services.token_service import TokenServicePort


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthenticateUser:
    def __init__(
        self,
        users: UserRepositoryPort,
        hasher: PasswordHasherPort,
        tokens: TokenServicePort,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def login(self, email: str, password: str) -> tuple[str, User]:
        email_n = email.strip().lower()
        user = await self._users.get_by_email(email_n)
        if not user or not self._hasher.verify(password, user.password_hash):
            raise AuthError("email ou senha inválidos")
        access = self._tokens.create_access_token(user.id, user.email, user.tenant_id)
        return access, user


class RegisterUser:
    def __init__(
        self,
        users: UserRepositoryPort,
        hasher: PasswordHasherPort,
        tenants: TenantRepositoryPort,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tenants = tenants

    async def execute(self, email: str, password: str, tenant_id: str | None = None) -> User:
        if len(password) < 8:
            raise ValidationError("senha deve ter pelo menos 8 caracteres")
        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValidationError("email inválido")
        if tenant_id and not await self._tenants.get_by_id(tenant_id):
            raise NotFoundError("tenant não encontrado")
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
        )
        await self._users.save(user)
        return user


class ChangePassword:
    def __init__(
        self,
        users: UserRepositoryPort,
        hasher: PasswordHasherPort,
    ) -> None:
        self._users = users
        self._hasher = hasher

    async def execute(self, user_id: str, current_password: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise ValidationError("nova senha deve ter pelo menos 8 caracteres")
        user = await self._users.get_by_id(user_id)
        if not user:
            raise AuthError("usuário não encontrado")
        if not self._hasher.verify(current_password, user.password_hash):
            raise AuthError("senha atual incorreta")
        updated = User(
            id=user.id,
            email=user.email,
            password_hash=self._hasher.hash(new_password),
            tenant_id=user.tenant_id,
            created_at=user.created_at,
            updated_at=_utcnow(),
        )
        await self._users.save(updated)


class RequestPasswordReset:
    def __init__(
        self,
        users: UserRepositoryPort,
        resets: PasswordResetRepositoryPort,
        email_sender: EmailSenderPort,
        code_ttl_minutes: int = 15,
    ) -> None:
        self._users = users
        self._resets = resets
        self._email_sender = email_sender
        self._ttl = code_ttl_minutes

    async def execute(self, email: str) -> None:
        """Sempre responde de forma uniforme (não revela se o email existe)."""
        email_n = email.strip().lower()
        user = await self._users.get_by_email(email_n)
        if user:
            code = f"{secrets.randbelow(1_000_000):06d}"
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            expires = _utcnow().replace(microsecond=0) + timedelta(minutes=self._ttl)
            await self._resets.save(
                PasswordResetRecord(email=email_n, code_hash=code_hash, expires_at=expires)
            )
            await self._email_sender.send_verification_code(email_n, code)


class ResetPasswordWithCode:
    def __init__(
        self,
        users: UserRepositoryPort,
        resets: PasswordResetRepositoryPort,
        hasher: PasswordHasherPort,
    ) -> None:
        self._users = users
        self._resets = resets
        self._hasher = hasher

    async def execute(self, email: str, code: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise ValidationError("nova senha deve ter pelo menos 8 caracteres")
        email_n = email.strip().lower()
        record = await self._resets.get_for_email(email_n)
        if not record:
            raise AuthError("código inválido ou expirado")
        if _utcnow() > record.expires_at:
            await self._resets.clear(email_n)
            raise AuthError("código inválido ou expirado")
        if hashlib.sha256(code.strip().encode()).hexdigest() != record.code_hash:
            raise AuthError("código inválido ou expirado")
        user = await self._users.get_by_email(email_n)
        if not user:
            await self._resets.clear(email_n)
            raise AuthError("código inválido ou expirado")
        updated = User(
            id=user.id,
            email=user.email,
            password_hash=self._hasher.hash(new_password),
            tenant_id=user.tenant_id,
            created_at=user.created_at,
            updated_at=_utcnow(),
        )
        await self._users.save(updated)
        await self._resets.clear(email_n)
