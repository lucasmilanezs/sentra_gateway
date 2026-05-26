from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Policy:
    id: str
    route_id: str
    requires_auth: bool = False
    rate_limit_per_minute: int | None = None
    allowed_roles: list[str] = field(default_factory=list)
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_clock_skew_seconds: int = 30
    required_headers: list[str] = field(default_factory=list)
    forbidden_headers: list[str] = field(default_factory=list)
    required_params: list[str] = field(default_factory=list)
    forbidden_params: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
