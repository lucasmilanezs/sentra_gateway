from dataclasses import dataclass, field
from datetime import datetime

from src.admin.domain.exceptions import ValidationError
from src.admin.domain.value_objects.permission import Permission


@dataclass
class User:

    id: str
    email: str
    password_hash: str
    tenant_id: str | None
    created_at: datetime
    updated_at: datetime
    role: str = "admin"
    permissions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.email = self.normalize_email(self.email)
        self.permissions = Permission.normalize_many(self.permissions)

        if self.role == "superuser":
            if self.tenant_id is not None:
                raise ValueError("Invariante violada: superuser não pode ter tenant_id")
        else:
            if not self.tenant_id:
                raise ValueError(
                    f"Invariante violada: usuário com role='{self.role}' exige tenant_id obrigatório"
                )

    @staticmethod
    def canonical_email(email: str) -> str:
        return (email or "").strip().lower()

    @classmethod
    def normalize_email(cls, email: str) -> str:
        normalized = cls.canonical_email(email)
        if not normalized or "@" not in normalized:
            raise ValidationError("email inválido")
        return normalized

    @staticmethod
    def ensure_valid_password(password: str, *, message: str = "senha deve ter pelo menos 8 caracteres") -> None:
        if len(password) < 8:
            raise ValidationError(message)

    @classmethod
    def create_admin(
        cls, *, id: str, email: str, password_hash: str, tenant_id: str, now: datetime
    ) -> "User":
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
            role="admin",
            permissions=[],
        )

    @classmethod
    def create_member(
        cls,
        *,
        id: str,
        email: str,
        password_hash: str,
        tenant_id: str,
        permissions: list[str],
        now: datetime,
    ) -> "User":
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
            role="member",
            permissions=permissions,
        )

    @classmethod
    def create_superuser(
        cls, *, id: str, email: str, password_hash: str, now: datetime
    ) -> "User":
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            tenant_id=None,
            created_at=now,
            updated_at=now,
            role="superuser",
            permissions=[],
        )

    def with_permissions(self, permissions: list[str], *, now: datetime) -> "User":
        if self.role != "member":
            raise ValidationError("permissões granulares só se aplicam a members")
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            tenant_id=self.tenant_id,
            created_at=self.created_at,
            updated_at=now,
            role=self.role,
            permissions=permissions,
        )
