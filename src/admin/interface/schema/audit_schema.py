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


class MetricsSummaryResponse(BaseModel):
    total_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    status_2xx: int
    status_4xx: int
    status_5xx: int
    top_routes: list[dict]
    window_hours: int = Field(default=24)
