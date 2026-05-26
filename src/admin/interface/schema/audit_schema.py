from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AuditRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str | None
    route_id: str | None
    method: str
    path: str
    upstream_url: str
    status_code: int
    latency_ms: float
    client_ip: str
    created_at: datetime
    outcome: str = "SUCCESS"
    denial_reason: str | None = None
    denial_check: str | None = None
    tenant_label: str | None = None
    route_label: str | None = None
    route_methods: str | None = None


class AuditFilteredResponse(BaseModel):
    items: list[AuditRequestResponse]
    total: int


class ChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str | None
    actor_id: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    resource_summary: str
    timestamp: datetime
    detail: str | None
    tenant_label: str | None = None
    actor_label: str | None = None
    resource_label: str | None = None


class ChangeEventFilteredResponse(BaseModel):
    items: list[ChangeEventResponse]
    total: int


class MetricsSummaryResponse(BaseModel):
    total_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    success_count: int = 0
    denied_count: int = 0
    upstream_errors: int = 0
    resolution_errors: int = 0
    status_2xx: int
    status_4xx: int
    status_5xx: int
    top_routes: list[dict]
    window_hours: int = Field(default=24)


class RawGatewayLogResponse(BaseModel):
    id: str
    timestamp: datetime | None
    tenant_id: str | None
    route_id: str | None
    method: str | None
    path: str | None
    status_code: int | None
    outcome: str
    latency_ms: float | None
    summary: str
    payload: dict
    tenant_label: str | None = None
    route_label: str | None = None
    policy_summary: str | None = None
    header_checks: list[dict] = Field(default_factory=list)
    param_checks: list[dict] = Field(default_factory=list)
    policy_checks: list[dict] = Field(default_factory=list)
    layer_errors: dict = Field(default_factory=dict)


class RawGatewayLogFilteredResponse(BaseModel):
    items: list[RawGatewayLogResponse]
    total: int
    source: str = "redis_streams"
