from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuditRequest:
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
