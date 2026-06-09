from datetime import datetime, timezone
from typing import Dict, Optional

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request


class LogEventBuilder:
    """Builds dense operational log events for gateway observability."""

    def build(
        self,
        request: Request,
        upstream_url: str,
        status_code: int,
        latency_ms: float,
        route_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        error: Optional[str] = None,
        outcome: str = "SUCCESS",
        policy_result: PolicyResult | None = None,
        upstream_response_headers: Optional[Dict[str, str]] = None,
        upstream_response_body: bytes | None = None,
        layer_errors: Optional[Dict[str, str]] = None,
    ) -> LogEvent:
        client_ip = self._client_ip(request)
        return LogEvent(
            timestamp=datetime.now(tz=timezone.utc),
            method=request.method.value,
            path=request.path,
            upstream_url=upstream_url,
            status_code=status_code,
            latency_ms=latency_ms,
            route_id=route_id,
            tenant_id=tenant_id,
            client_ip=client_ip,
            error=error,
            outcome=outcome,
            request_headers=dict(request.headers),
            query_params=dict(request.query_params),
            policy_checks=self._policy_checks(policy_result),
            upstream_response_headers=upstream_response_headers or {},
            upstream_response_body_preview=self._body_preview(upstream_response_body),
            layer_errors=layer_errors or {},
        )

    @staticmethod
    def _client_ip(request: Request) -> str:
        raw = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or "unknown"
        return raw.split(",")[0].strip()

    @staticmethod
    def _policy_checks(policy_result: PolicyResult | None) -> list[dict]:
        if not policy_result or not policy_result.checks:
            return []
        return [
            {"check": check.check, "passed": check.passed, "detail": check.detail}
            for check in policy_result.checks
        ]

    @staticmethod
    def _body_preview(body: bytes | None) -> str:
        if not body:
            return ""
        try:
            return body[:512].decode("utf-8", errors="replace")
        except Exception:
            return ""
