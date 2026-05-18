from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LogEvent:
    """
    Operational log entry for a single processed request.

    Distinct from audit records:
      - Logs are internal observability data with a short lifecycle.
      - Audit records are structured evidence persisted in PostgreSQL
        with defined retention, exposed to operators for traceability.

    Log events are never exposed to tenants and are not governance data.
    """

    timestamp: datetime
    method: str
    path: str
    upstream_url: str
    status_code: int
    latency_ms: float
    route_id: Optional[str] = None
    tenant_id: Optional[str] = None
    client_ip: Optional[str] = None
    error: Optional[str] = None
