class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class AuthError(DomainError):
    pass


class ValidationError(DomainError):
    pass
