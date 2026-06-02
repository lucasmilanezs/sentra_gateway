from dataclasses import dataclass, field
from typing import ClassVar, Optional, Tuple


@dataclass(frozen=True)
class Policy:
    AUTH_NONE: ClassVar[str] = "none"
    AUTH_BEARER: ClassVar[str] = "bearer"
    AUTH_JWT_STRUCTURAL: ClassVar[str] = "jwt_structural"
    AUTH_JWT_CLAIMS: ClassVar[str] = "jwt_claims"
    AUTH_JWT_SIGNED: ClassVar[str] = "jwt_signed"
    VALID_AUTH_MODES: ClassVar[set[str]] = {
        AUTH_NONE,
        AUTH_BEARER,
        AUTH_JWT_STRUCTURAL,
        AUTH_JWT_CLAIMS,
        AUTH_JWT_SIGNED,
    }

    id: str
    route_id: str
    requires_auth: bool = False
    rate_limit_per_minute: Optional[int] = None
    # Deprecated: retained only for backwards-compatible snapshots. Not enforced by Gateway.
    allowed_roles: Tuple[str, ...] = field(default_factory=tuple)
    auth_mode: str | None = None
    jwt_validate_exp: bool = True
    jwt_issuer: Optional[str] = None
    jwt_audience: Optional[str] = None
    jwt_clock_skew_seconds: int = 30
    jwt_signing_algorithm: Optional[str] = None
    jwt_signing_key: Optional[str] = None
    jwt_signing_key_configured: bool = False
    jwt_signing_key_hint: Optional[str] = None
    required_headers: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_headers: Tuple[str, ...] = field(default_factory=tuple)
    required_params: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_params: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        auth_mode = self._normalize_auth_mode(self.auth_mode, self.requires_auth, self.jwt_validate_exp)
        object.__setattr__(self, "auth_mode", auth_mode)
        object.__setattr__(self, "requires_auth", auth_mode != self.AUTH_NONE)
        if self.jwt_clock_skew_seconds < 0:
            object.__setattr__(self, "jwt_clock_skew_seconds", 0)

    @classmethod
    def _normalize_auth_mode(cls, auth_mode: str | None, requires_auth: bool, jwt_validate_exp: bool) -> str:
        if not auth_mode:
            if not requires_auth:
                return cls.AUTH_NONE
            return cls.AUTH_JWT_CLAIMS if jwt_validate_exp else cls.AUTH_JWT_STRUCTURAL
        normalized = auth_mode.strip().lower()
        return normalized if normalized in cls.VALID_AUTH_MODES else cls.AUTH_NONE
