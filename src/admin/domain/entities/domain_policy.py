from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class DomainPolicy:
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
    VALID_SIGNING_ALGORITHMS: ClassVar[set[str]] = {
        "HS256", "HS384", "HS512",
        "RS256", "RS384", "RS512",
    }

    id: str
    domain_id: str
    requires_auth: bool = False
    rate_limit_per_minute: int | None = None
    # Deprecated: kept for backward compatibility with older persisted rows/API clients.
    # Gateway authorization by application roles is intentionally not enforced anymore.
    allowed_roles: list[str] = field(default_factory=list)
    auth_mode: str | None = None
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_clock_skew_seconds: int = 30
    jwt_signing_algorithm: str | None = None
    jwt_signing_key: str | None = None  # write-only transient plaintext received from admin UI
    jwt_signing_key_configured: bool = False
    jwt_signing_key_hint: str | None = None
    required_headers: list[str] = field(default_factory=list)
    forbidden_headers: list[str] = field(default_factory=list)
    required_params: list[str] = field(default_factory=list)
    forbidden_params: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.auth_mode = self.normalize_auth_mode(self.auth_mode, self.requires_auth, self.jwt_validate_exp)
        self.requires_auth = self.auth_mode != self.AUTH_NONE
        self.jwt_signing_algorithm = self.normalize_signing_algorithm(self.jwt_signing_algorithm)
        self.jwt_clock_skew_seconds = self.normalize_clock_skew(self.jwt_clock_skew_seconds)

    @classmethod
    def normalize_auth_mode(cls, auth_mode: str | None, requires_auth: bool = False, jwt_validate_exp: bool = True) -> str:
        if not auth_mode:
            if not requires_auth:
                return cls.AUTH_NONE
            return cls.AUTH_JWT_CLAIMS if jwt_validate_exp else cls.AUTH_JWT_STRUCTURAL
        normalized = auth_mode.strip().lower()
        if normalized not in cls.VALID_AUTH_MODES:
            raise ValueError(f"Invalid auth_mode: {auth_mode}")
        return normalized

    @classmethod
    def normalize_signing_algorithm(cls, algorithm: str | None) -> str | None:
        if not algorithm:
            return None
        normalized = algorithm.strip().upper()
        if normalized not in cls.VALID_SIGNING_ALGORITHMS:
            raise ValueError(f"Unsupported JWT signing algorithm: {algorithm}")
        return normalized

    @staticmethod
    def normalize_clock_skew(value: int | None) -> int:
        if value is None:
            return 30
        value = int(value)
        if value < 0 or value > 300:
            raise ValueError("jwt_clock_skew_seconds must be between 0 and 300.")
        return value
