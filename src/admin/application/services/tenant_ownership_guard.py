from src.admin.domain.exceptions import AuthError


class TenantOwnershipGuard:
    """
    Guard centralizado de isolamento entre tenants.

    Encapsula a única regra de ownership do sistema:
      - superuser acessa qualquer tenant
      - qualquer outro role só acessa o próprio tenant

    Uso nos use cases:

        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )

    Raises AuthError (→ HTTP 401 via exception handler existente),
    consistente com o padrão já estabelecido em ManageSubUser.
    """

    @staticmethod
    def assert_access(
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        resource_tenant_id: str,
    ) -> None:
        if caller_role == "superuser":
            return
        if caller_tenant_id != resource_tenant_id:
            raise AuthError("acesso negado ao tenant")
