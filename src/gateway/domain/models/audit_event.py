from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuditEvent:
    id: str
    timestamp: datetime
    tenant_id: Optional[str]
    route_id: Optional[str]
    method: str
    path: str
    client_ip: str
    outcome: str
    denial_reason: Optional[str] = None
    denial_check: Optional[str] = None
    upstream_url: Optional[str] = None
    upstream_status_code: Optional[int] = None
    latency_ms: Optional[float] = None
