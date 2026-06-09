from dataclasses import dataclass, field


@dataclass(frozen=True)
class JwtClaims:
    """Validated JWT claims used by the admin plane."""

    sub: str
    email: str
    tenant_id: str | None = None
    role: str | None = None
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def is_superuser(self) -> bool:
        return self.role == "superuser"

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_admin_like(self) -> bool:
        return self.is_superuser() or self.is_admin()

    def has_permission(self, permission: str) -> bool:
        if self.is_admin_like():
            return True
        return permission in self.permissions

    def resolve_tenant_scope(self, requested_tenant_id: str | None) -> str | None:
        if self.is_superuser():
            return requested_tenant_id
        return self.tenant_id
