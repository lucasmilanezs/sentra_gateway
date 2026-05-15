from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PolicyUpsert(BaseModel):
    requires_auth: bool = False
    rate_limit_per_minute: int | None = Field(default=None, gt=0)
    allowed_roles: list[str] = Field(default_factory=list)


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    route_id: str
    requires_auth: bool
    rate_limit_per_minute: int | None
    allowed_roles: list[str]
    created_at: datetime
    updated_at: datetime