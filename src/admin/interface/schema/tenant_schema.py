from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    alias: str = Field(min_length=1, max_length=128)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    alias: str | None = Field(default=None, min_length=1, max_length=128)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    alias: str
    created_at: datetime
    updated_at: datetime


# ── TenantDomain schemas ────────────────────────────────────────────────

class TenantDomainCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)


class TenantDomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    domain: str
    created_at: datetime
    updated_at: datetime


# ── DomainPolicy schemas ─────────────────────────────────

AUTH_MODES = {"none", "bearer", "jwt_structural", "jwt_claims", "jwt_signed"}


class DomainPolicyUpsert(BaseModel):
    auth_mode: str = Field(default="none", description="none, bearer, jwt_structural, jwt_claims or jwt_signed")
    # Backward-compatible input. If provided by older clients, auth_mode wins.
    requires_auth: bool | None = None
    rate_limit_per_minute: int | None = Field(default=None, gt=0)

    # Deprecated: Gateway no longer enforces application roles/scopes.
    allowed_roles: list[str] = Field(default_factory=list)

    jwt_validate_exp: bool = True
    jwt_issuer: str | None = Field(default=None, max_length=255)
    jwt_audience: str | None = Field(default=None, max_length=255)
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    jwt_signing_algorithm: str | None = Field(default=None, max_length=32)
    # Write-only. Never returned by API responses.
    jwt_signing_key: str | None = Field(default=None, max_length=12000)

    required_headers: list[str] = Field(default_factory=list)
    forbidden_headers: list[str] = Field(default_factory=list)
    required_params: list[str] = Field(default_factory=list)
    forbidden_params: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "DomainPolicyUpsert":
        self.auth_mode = (self.auth_mode or "none").strip().lower()
        if self.auth_mode not in AUTH_MODES:
            raise ValueError("auth_mode inválido")
        if self.requires_auth is not None and self.auth_mode == "none" and self.requires_auth:
            self.auth_mode = "jwt_claims" if self.jwt_validate_exp else "jwt_structural"
        if self.auth_mode == "jwt_signed":
            self.jwt_signing_algorithm = (self.jwt_signing_algorithm or "HS256").strip().upper()
        elif self.jwt_signing_algorithm:
            self.jwt_signing_algorithm = self.jwt_signing_algorithm.strip().upper()
        return self


class DomainPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    auth_mode: str
    requires_auth: bool
    rate_limit_per_minute: int | None
    # Deprecated; kept for compatibility during UI/API transition.
    allowed_roles: list[str]
    jwt_validate_exp: bool
    jwt_issuer: str | None
    jwt_audience: str | None
    jwt_clock_skew_seconds: int
    jwt_signing_algorithm: str | None
    jwt_signing_key_configured: bool = False
    jwt_signing_key_hint: str | None = None
    required_headers: list[str]
    forbidden_headers: list[str]
    required_params: list[str]
    forbidden_params: list[str]
    created_at: datetime
    updated_at: datetime



class DomainSuggestionsResponse(BaseModel):
    suggestions: list[str]
    group_label: str
