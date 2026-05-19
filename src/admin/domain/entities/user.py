from dataclasses import dataclass, field
from datetime import datetime


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
        if self.role == "superuser":
            if self.tenant_id is not None:
                raise ValueError(
                    "Invariante violada: superuser não pode ter tenant_id"
                )
        else:
            if not self.tenant_id:
                raise ValueError(
                    f"Invariante violada: usuário com role='{self.role}' "
                    "exige tenant_id obrigatório"
                )