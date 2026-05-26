from dataclasses import dataclass
from datetime import datetime
import re

from src.admin.domain.exceptions import ValidationError

_ALIAS_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class Tenant:
    id: str
    name: str
    alias: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.name = self.normalize_name(self.name)
        self.alias = self.normalize_alias(self.alias)

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = (name or "").strip()
        if not normalized or len(normalized) > 255:
            raise ValidationError("nome da empresa inválido")
        return normalized

    @staticmethod
    def normalize_alias(alias: str) -> str:
        normalized = (alias or "").strip().lower()
        if not normalized or len(normalized) > 128:
            raise ValidationError("alias inválido")
        if not _ALIAS_RE.match(normalized):
            raise ValidationError("alias deve conter apenas letras minúsculas, números e hífens")
        return normalized

    @classmethod
    def create(cls, *, id: str, name: str, alias: str, now: datetime) -> "Tenant":
        return cls(id=id, name=name, alias=alias, created_at=now, updated_at=now)

    def with_updates(self, *, name: str | None = None, alias: str | None = None, now: datetime) -> "Tenant":
        return Tenant(
            id=self.id,
            name=self.name if name is None else name,
            alias=self.alias if alias is None else alias,
            created_at=self.created_at,
            updated_at=now,
        )

    def domain_suggestions(self) -> list[str]:
        return [
            f"api.{self.alias}.local",
            f"gateway.{self.alias}.corp",
            f"{self.alias}.internal",
        ]
