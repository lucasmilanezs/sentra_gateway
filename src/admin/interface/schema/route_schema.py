from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.admin.domain.value_objects.http_method import HttpMethod


class AdminRouteCreate(BaseModel):
    tenant_id: str
    path_pattern: str = Field(min_length=1, max_length=512)
    method: HttpMethod
    backend_url: str = Field(min_length=1, max_length=2048)


class AdminRouteUpdate(BaseModel):
    path_pattern: str | None = Field(default=None, min_length=1, max_length=512)
    method: HttpMethod | None = None
    backend_url: str | None = Field(default=None, min_length=1, max_length=2048)


class AdminRouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    path_pattern: str
    method: HttpMethod
    backend_url: str
    created_at: datetime
    updated_at: datetime
