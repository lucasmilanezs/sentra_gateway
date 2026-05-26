from __future__ import annotations

from src.admin.domain.exceptions import AuthError


class TenantAccessControl:
    """Domain service that enforces tenant isolation rules.

    Business invariant:
    - superuser can operate across tenants;
    - every other role is restricted to its own tenant.
    """

    @staticmethod
    def ensure_tenant_access(
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        resource_tenant_id: str,
    ) -> None:
        if caller_role == "superuser":
            return
        if caller_tenant_id != resource_tenant_id:
            raise AuthError("acesso negado ao tenant")

    # Compatibility alias for the older guard naming used by existing use cases.
    assert_access = ensure_tenant_access
