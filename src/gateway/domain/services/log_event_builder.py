from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.models.request import Request


class LogEventBuilder:

    def build(
        self, request: Request, upstream_url: str, status_code: int, latency_ms: float,
        route_id: Optional[str] = None, tenant_id: Optional[str] = None,
        error: Optional[str] = None, outcome: str = "SUCCESS",
        policy_checks: Optional[List[dict]] = None,
        upstream_response_headers: Optional[Dict[str, str]] = None,
        upstream_response_body_preview: str = "",
        layer_errors: Optional[Dict[str, str]] = None,
    ) -> LogEvent:
        client_ip = (request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or "unknown")
        return LogEvent(
            timestamp=datetime.now(tz=timezone.utc), method=request.method.value,
            path=request.path, upstream_url=upstream_url, status_code=status_code,
            latency_ms=latency_ms, route_id=route_id, tenant_id=tenant_id,
            client_ip=client_ip.split(",")[0].strip(), error=error, outcome=outcome,
            request_headers=dict(request.headers), query_params=dict(request.query_params),
            policy_checks=policy_checks or [],
            upstream_response_headers=upstream_response_headers or {},
            upstream_response_body_preview=upstream_response_body_preview,
            layer_errors=layer_errors or {},
        )
