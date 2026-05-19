from dataclasses import dataclass, field


@dataclass(frozen=True)
class JwtClaims:
    """
    Claims validados a partir do token JWT.

    permissions é uma tupla de strings (imutável, como o dataclass exige)
    contendo as permissões granulares do usuário. Vazia para superuser e
    admin (acesso total implícito). Populada para role="member".
    """

    sub: str
    email: str
    tenant_id: str | None = None
    role: str | None = None
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def has_permission(self, permission: str) -> bool:
        """
        Retorna True se o usuário tem acesso à permissão solicitada.

        superuser e admin têm acesso total implícito.
        member precisa ter a permissão explicitamente listada.
        """
        if self.role in ("superuser", "admin"):
            return True
        return permission in self.permissions