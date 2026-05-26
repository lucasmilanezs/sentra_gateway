class GatewayDomainError(Exception):
    """Base para todos os erros do domínio gateway."""

class TenantNotFoundError(GatewayDomainError):
    """Nenhum tenant registrado para o Host header recebido."""

class RouteNotFoundError(GatewayDomainError):
    """Nenhuma rota correspondeu ao path/método da requisição."""

class DomainNotFoundError(GatewayDomainError):
    """Domínio referenciado pela rota não está configurado."""

class PolicyDeniedError(GatewayDomainError):
    def __init__(self, reason: str, status_code: int = 403) -> None:
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)

class UpstreamError(GatewayDomainError):
    error_type: str = "UPSTREAM_ERROR"
    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

class UpstreamTimeoutError(UpstreamError):
    error_type = "UPSTREAM_TIMEOUT"

class UpstreamConnectionRefusedError(UpstreamError):
    error_type = "UPSTREAM_CONNECTION_REFUSED"

class UpstreamDNSError(UpstreamError):
    error_type = "UPSTREAM_DNS_FAILURE"

class UpstreamUnreachableError(UpstreamError):
    error_type = "UPSTREAM_UNREACHABLE"
