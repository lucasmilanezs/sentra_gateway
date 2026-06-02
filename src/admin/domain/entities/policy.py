from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from src.admin.domain.exceptions import ValidationError
from src.shared.http.headers import Headers
from src.shared.http.params import Params


@dataclass
class Policy:
    """Security policy bound to either a route or a tenant domain.

    Route policies and domain fallback policies are the same business concept.
    The only difference is their attachment point. Exactly one target must be set.
    """

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
    route_id: str | None = None
    domain_id: str | None = None
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
        self.route_id = self._normalize_optional_id(self.route_id)
        self.domain_id = self._normalize_optional_id(self.domain_id)
        self._ensure_single_target()
        self.auth_mode = self.normalize_auth_mode(self.auth_mode, self.requires_auth, self.jwt_validate_exp)
        self.requires_auth = self.auth_mode != self.AUTH_NONE
        self.rate_limit_per_minute = self.normalize_rate_limit(self.rate_limit_per_minute)
        self.jwt_signing_algorithm = self.normalize_signing_algorithm(self.jwt_signing_algorithm)
        if self.auth_mode != self.AUTH_JWT_SIGNED:
            self.jwt_signing_algorithm = None
            self.jwt_signing_key = None
            self.jwt_signing_key_configured = False
            self.jwt_signing_key_hint = None
        self.jwt_clock_skew_seconds = self.normalize_clock_skew(self.jwt_clock_skew_seconds)
        self.required_headers = self.normalize_headers(self.required_headers)
        self.forbidden_headers = self.normalize_headers(self.forbidden_headers)
        self.required_params = self.normalize_params(self.required_params)
        self.forbidden_params = self.normalize_params(self.forbidden_params)
        self.ensure_signing_material_available()

    @classmethod
    def create_for_route(cls, *, id: str, route_id: str, now: datetime, **kwargs) -> "Policy":
        return cls(id=id, route_id=route_id, domain_id=None, created_at=kwargs.pop("created_at", now), updated_at=now, **kwargs)

    @classmethod
    def create_for_domain(cls, *, id: str, domain_id: str, now: datetime, **kwargs) -> "Policy":
        return cls(id=id, route_id=None, domain_id=domain_id, created_at=kwargs.pop("created_at", now), updated_at=now, **kwargs)

    def reconfigure(self, *, now: datetime, **changes) -> "Policy":
        data = {
            "id": self.id,
            "route_id": self.route_id,
            "domain_id": self.domain_id,
            "requires_auth": self.requires_auth,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "allowed_roles": list(self.allowed_roles),
            "auth_mode": self.auth_mode,
            "jwt_validate_exp": self.jwt_validate_exp,
            "jwt_issuer": self.jwt_issuer,
            "jwt_audience": self.jwt_audience,
            "jwt_clock_skew_seconds": self.jwt_clock_skew_seconds,
            "jwt_signing_algorithm": self.jwt_signing_algorithm,
            "jwt_signing_key": None,
            "jwt_signing_key_configured": self.jwt_signing_key_configured,
            "jwt_signing_key_hint": self.jwt_signing_key_hint,
            "required_headers": list(self.required_headers),
            "forbidden_headers": list(self.forbidden_headers),
            "required_params": list(self.required_params),
            "forbidden_params": list(self.forbidden_params),
            "created_at": self.created_at,
            "updated_at": now,
        }
        data.update(changes)
        return Policy(**data)

    @staticmethod
    def _normalize_optional_id(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _ensure_single_target(self) -> None:
        if bool(self.route_id) == bool(self.domain_id):
            raise ValidationError("policy deve estar vinculada a uma rota ou a um domain, nunca ambos")

    def is_route_policy(self) -> bool:
        return self.route_id is not None

    def is_domain_policy(self) -> bool:
        return self.domain_id is not None

    def target_id(self) -> str:
        return self.route_id or self.domain_id or ""

    def target_type(self) -> str:
        return "route" if self.is_route_policy() else "domain"

    def audit_resource_type(self) -> str:
        return "policy" if self.is_route_policy() else "domain_policy"

    def audit_detail(self) -> dict:
        detail = {
            "auth_mode": self.auth_mode,
            "requires_auth": self.requires_auth,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "required_headers": list(self.required_headers),
            "forbidden_headers": list(self.forbidden_headers),
            "required_params": list(self.required_params),
            "forbidden_params": list(self.forbidden_params),
        }
        if self.is_route_policy():
            detail["route_id"] = self.route_id
        else:
            detail["domain_id"] = self.domain_id
        return detail

    def ensure_signing_material_available(self) -> None:
        if self.auth_mode != self.AUTH_JWT_SIGNED:
            return
        if self.jwt_signing_key or self.jwt_signing_key_configured:
            return
        raise ValidationError("Validação de assinatura JWT exige uma secret/chave pública configurada.")

    @classmethod
    def normalize_auth_mode(cls, auth_mode: str | None, requires_auth: bool = False, jwt_validate_exp: bool = True) -> str:
        if not auth_mode:
            if not requires_auth:
                return cls.AUTH_NONE
            return cls.AUTH_JWT_CLAIMS if jwt_validate_exp else cls.AUTH_JWT_STRUCTURAL
        normalized = auth_mode.strip().lower()
        if normalized not in cls.VALID_AUTH_MODES:
            raise ValidationError(f"auth_mode inválido: {auth_mode}")
        return normalized

    @classmethod
    def normalize_signing_algorithm(cls, algorithm: str | None) -> str | None:
        if not algorithm:
            return None
        normalized = algorithm.strip().upper()
        if normalized not in cls.VALID_SIGNING_ALGORITHMS:
            raise ValidationError(f"algoritmo JWT não suportado: {algorithm}")
        return normalized

    @staticmethod
    def normalize_clock_skew(value: int | None) -> int:
        if value is None:
            return 30
        value = int(value)
        if value < 0 or value > 300:
            raise ValidationError("jwt_clock_skew_seconds deve estar entre 0 e 300")
        return value

    @staticmethod
    def normalize_rate_limit(value: int | None) -> int | None:
        if value is None:
            return None
        value = int(value)
        if value <= 0:
            raise ValidationError("rate_limit_per_minute deve ser positivo")
        return value

    @staticmethod
    def normalize_headers(values: list[str] | None) -> list[str]:
        try:
            return Headers.from_names(values or []).to_list()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    @staticmethod
    def normalize_params(values: list[str] | None) -> list[str]:
        try:
            return Params.from_names(values or []).to_list()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
