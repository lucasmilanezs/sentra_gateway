from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PolicyUpsert(BaseModel):
    requires_auth: bool = False
    rate_limit_per_minute: int | None = Field(default=None, gt=0)
    allowed_roles: list[str] = Field(default_factory=list)
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = Field(default=None, max_length=255)
    jwt_audience: str | None = Field(default=None, max_length=255)
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    required_headers: list[str] = Field(default_factory=list)
    forbidden_headers: list[str] = Field(default_factory=list)
    required_params: list[str] = Field(default_factory=list)
    forbidden_params: list[str] = Field(default_factory=list)


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    route_id: str
    requires_auth: bool
    rate_limit_per_minute: int | None
    allowed_roles: list[str]
    jwt_validate_exp: bool
    jwt_issuer: str | None
    jwt_audience: str | None
    jwt_clock_skew_seconds: int
    required_headers: list[str]
    forbidden_headers: list[str]
    required_params: list[str]
    forbidden_params: list[str]
    created_at: datetime
    updated_at: datetime
