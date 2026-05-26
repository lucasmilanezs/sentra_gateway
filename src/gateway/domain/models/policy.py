from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class Policy:
    id: str
    route_id: str
    requires_auth: bool = False
    rate_limit_per_minute: Optional[int] = None
    allowed_roles: Tuple[str, ...] = field(default_factory=tuple)
    jwt_validate_exp: bool = True
    jwt_issuer: Optional[str] = None
    jwt_audience: Optional[str] = None
    jwt_clock_skew_seconds: int = 30
    required_headers: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_headers: Tuple[str, ...] = field(default_factory=tuple)
    required_params: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_params: Tuple[str, ...] = field(default_factory=tuple)
