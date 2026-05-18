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
