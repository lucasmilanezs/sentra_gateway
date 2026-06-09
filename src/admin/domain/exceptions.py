class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class AuthError(DomainError):
    """Authentication failure: missing, invalid or expired credentials. Maps to HTTP 401."""
    pass


class ForbiddenError(DomainError):
    """Authorization failure: authenticated caller is not allowed to perform the action. Maps to HTTP 403."""
    pass


class ValidationError(DomainError):
    pass
