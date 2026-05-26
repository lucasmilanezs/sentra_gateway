import uuid
from datetime import datetime, timezone
from typing import Optional

from src.gateway.domain.models.audit_event import AuditEvent
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request


class AuditEventBuilder:

    @staticmethod
    def _client_ip(request: Request) -> str:
        raw = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or "unknown"
        return raw.split(",")[0].strip()

    def build_success(self, *, request, tenant_id, route_id, upstream_url, upstream_status_code, latency_ms):
        return AuditEvent(
            id=str(uuid.uuid4()), timestamp=datetime.now(tz=timezone.utc),
            tenant_id=tenant_id, route_id=route_id, method=request.method.value,
            path=request.path, client_ip=self._client_ip(request), outcome="SUCCESS",
            upstream_url=upstream_url, upstream_status_code=upstream_status_code, latency_ms=latency_ms,
        )

    def build_resolution_failure(self, *, request, outcome, tenant_id=None, route_id=None):
        return AuditEvent(
            id=str(uuid.uuid4()), timestamp=datetime.now(tz=timezone.utc),
            tenant_id=tenant_id, route_id=route_id, method=request.method.value,
            path=request.path, client_ip=self._client_ip(request), outcome=outcome,
        )

    def build_policy_denial(self, *, request, tenant_id, route_id, policy_result):
        first_failed = next((c for c in policy_result.checks if not c.passed), None)
        return AuditEvent(
            id=str(uuid.uuid4()), timestamp=datetime.now(tz=timezone.utc),
            tenant_id=tenant_id, route_id=route_id, method=request.method.value,
            path=request.path, client_ip=self._client_ip(request), outcome="POLICY_DENIED",
            denial_reason=policy_result.reason,
            denial_check=first_failed.check if first_failed else None,
        )

    def build_upstream_failure(self, *, request, tenant_id, route_id, upstream_url, error_type, error_message, latency_ms):
        return AuditEvent(
            id=str(uuid.uuid4()), timestamp=datetime.now(tz=timezone.utc),
            tenant_id=tenant_id, route_id=route_id, method=request.method.value,
            path=request.path, client_ip=self._client_ip(request), outcome=error_type,
            upstream_url=upstream_url, denial_reason=error_message, latency_ms=latency_ms,
        )
