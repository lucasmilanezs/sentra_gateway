from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LogEvent:
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
    outcome: str = "SUCCESS"
    request_headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    policy_checks: List[dict] = field(default_factory=list)
    upstream_response_headers: Dict[str, str] = field(default_factory=dict)
    upstream_response_body_preview: str = ""
    layer_errors: Dict[str, str] = field(default_factory=dict)
