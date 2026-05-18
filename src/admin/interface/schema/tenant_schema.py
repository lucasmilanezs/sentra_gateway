from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


# ── DomainPolicy schemas ────────────────────────────────────────────────

class DomainPolicyUpsert(BaseModel):
    requires_auth: bool = False
    rate_limit_per_minute: int | None = Field(default=None, gt=0)
    allowed_roles: list[str] = Field(default_factory=list)
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = Field(default=None, max_length=255)
    jwt_audience: str | None = Field(default=None, max_length=255)
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)


class DomainPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    domain_id: str
    requires_auth: bool
    rate_limit_per_minute: int | None
    allowed_roles: list[str]
    jwt_validate_exp: bool
    jwt_issuer: str | None
    jwt_audience: str | None
    jwt_clock_skew_seconds: int
    created_at: datetime
    updated_at: datetime


class DomainSuggestionsResponse(BaseModel):
    suggestions: list[str]
    group_label: str
