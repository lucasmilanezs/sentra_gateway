from dataclasses import dataclass


@dataclass(frozen=True)
class JwtClaims:
    """Claims validados a partir do token JWT (sub = id do usuário)."""

    sub: str
    email: str
    tenant_id: str | None = None
