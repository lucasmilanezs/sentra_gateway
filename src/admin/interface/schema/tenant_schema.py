from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=128)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
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


class DomainPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    domain_id: str
    requires_auth: bool
    rate_limit_per_minute: int | None
    allowed_roles: list[str]
    created_at: datetime
    updated_at: datetime
