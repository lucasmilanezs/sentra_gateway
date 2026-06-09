from __future__ import annotations

from src.admin.domain.exceptions import ValidationError


def ensure_valid_rate_limit(rate_limit_per_minute: int | None) -> None:
    """Validate the shared domain invariant for route/domain/global policies."""
    if rate_limit_per_minute is not None and rate_limit_per_minute <= 0:
        raise ValidationError("rate_limit_per_minute deve ser maior que zero")
