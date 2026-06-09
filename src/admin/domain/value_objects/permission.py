from enum import Enum

from src.admin.domain.exceptions import ValidationError


class Permission(str, Enum):
    ROUTES = "routes"
    POLICIES = "policies"
    DOMAINS = "domains"
    AUDIT = "audit"
    METRICS = "metrics"
    MEMBERS = "members"

    @classmethod
    def values(cls) -> set[str]:
        return {p.value for p in cls}

    @classmethod
    def normalize_many(cls, permissions: list[str], *, require_non_empty: bool = False) -> list[str]:
        valid = cls.values()
        invalid = [p for p in permissions if p not in valid]
        if invalid:
            raise ValidationError(
                f"permissões inválidas: {invalid}. Válidas: {sorted(valid)}"
            )
        seen: set[str] = set()
        normalized = [p for p in permissions if not (p in seen or seen.add(p))]
        if require_non_empty and not normalized:
            raise ValidationError("sub-usuário deve ter ao menos uma permissão")
        return normalized
