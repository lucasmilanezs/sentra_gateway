import time
from typing import Optional

from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.application.ports.gateway_request_port import GatewayRequestPort
from src.gateway.application.use_cases.apply_policy_pipeline import ApplyPolicyPipeline
from src.gateway.domain.exceptions import (
    DomainNotFoundError, PolicyDeniedError, RouteNotFoundError,
    TenantNotFoundError, UpstreamError,
)
from src.gateway.domain.models.audit_event import AuditEvent
from src.gateway.domain.models.request import Request
from src.gateway.domain.ports.audit_port import AuditPort
from src.gateway.domain.ports.domain_repository import DomainRepository
from src.gateway.domain.ports.log_port import LogPort
from src.gateway.domain.ports.policy_repository import PolicyRepository
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.domain.ports.upstream_proxy_port import UpstreamProxyPort
from src.gateway.domain.services.audit_event_builder import AuditEventBuilder
from src.gateway.domain.services.log_event_builder import LogEventBuilder

# Backward-compat re-exports so nothing outside breaks
__all__ = [
    "TenantNotFoundError", "RouteNotFoundError",
    "DomainNotFoundError", "PolicyDeniedError", "ForwardRequest",
]


class ForwardRequest(GatewayRequestPort):

    def __init__(
        self, route_repository: RouteRepository, domain_repository: DomainRepository,
        policy_repository: PolicyRepository, proxy: UpstreamProxyPort,
        log_port: LogPort, policy_pipeline: ApplyPolicyPipeline,
        log_event_builder: LogEventBuilder, tenant_repository=None,
        audit_port: Optional[AuditPort] = None,
        audit_event_builder: Optional[AuditEventBuilder] = None,
    ) -> None:
        self._routes = route_repository
        self._domains = domain_repository
        self._policies = policy_repository
        self._proxy = proxy
        self._log = log_port
        self._pipeline = policy_pipeline
        self._log_event_builder = log_event_builder
        self._tenants = tenant_repository
        self._audit = audit_port
        self._audit_builder = audit_event_builder or AuditEventBuilder()

    async def handle(self, request: Request, raw_body: bytes) -> GatewayResponse:
        start = time.monotonic()

        # 0. Tenant resolution
        tenant = await self._tenants.get_by_domain(request.host)
        if tenant is None:
            await self._emit_audit(self._audit_builder.build_resolution_failure(
                request=request, outcome="TENANT_NOT_FOUND"))
            raise TenantNotFoundError(f"No tenant registered for host '{request.host}'.")

        # 1. Route resolution
        route = await self._routes.get_by_path(request.path, request.method.value, tenant.id)
        if route is None:
            await self._emit_audit(self._audit_builder.build_resolution_failure(
                request=request, outcome="ROUTE_NOT_FOUND", tenant_id=tenant.id))
            raise RouteNotFoundError(f"No route matched path '{request.path}' [{request.method.value}].")

        # 2. Domain resolution
        domain = await self._domains.get_by_id(route.domain_id)
        if domain is None:
            await self._emit_audit(self._audit_builder.build_resolution_failure(
                request=request, outcome="DOMAIN_NOT_FOUND", tenant_id=tenant.id, route_id=route.id))
            raise DomainNotFoundError(f"Domain '{route.domain_id}' referenced by route '{route.id}' is not configured.")

        # 3. Policy enforcement
        policy = await self._policies.get_by_route_id(route.id)
        if policy is None and hasattr(self._policies, "get_domain_policy"):
            policy = self._policies.get_domain_policy(request.host)

        result = await self._pipeline.apply(policy, request, tenant_id=tenant.id, route_id=route.id)
        if not result.allowed:
            await self._emit_audit(self._audit_builder.build_policy_denial(
                request=request, tenant_id=tenant.id, route_id=route.id, policy_result=result))
            raise PolicyDeniedError(reason=result.reason or "Request denied by policy.", status_code=result.status_code)

        # 4. Forward
        upstream_path = route.strip_prefix(request.path)
        upstream_url = domain.backend_url.build_upstream(upstream_path)

        try:
            upstream_response = await self._proxy.forward(
                method=request.method.value, url=upstream_url,
                headers=request.headers, body=raw_body, query_params=request.query_params)
        except UpstreamError as exc:
            latency_ms = (time.monotonic() - start) * 1000
            await self._emit_audit(self._audit_builder.build_upstream_failure(
                request=request, tenant_id=tenant.id, route_id=route.id,
                upstream_url=upstream_url, error_type=exc.error_type,
                error_message=str(exc), latency_ms=latency_ms))
            raise

        latency_ms = (time.monotonic() - start) * 1000

        # 5. Audit (success)
        await self._emit_audit(self._audit_builder.build_success(
            request=request, tenant_id=tenant.id, route_id=route.id,
            upstream_url=upstream_url, upstream_status_code=upstream_response.status_code,
            latency_ms=latency_ms))

        # 6. Operational log (enriched)
        body_preview = ""
        try:
            body_preview = upstream_response.body[:512].decode("utf-8", errors="replace")
        except Exception:
            pass

        policy_checks_data = [{"check": c.check, "passed": c.passed, "detail": c.detail} for c in result.checks] if result.checks else []

        log_event = self._log_event_builder.build(
            request=request, upstream_url=upstream_url,
            status_code=upstream_response.status_code, latency_ms=latency_ms,
            route_id=route.id, tenant_id=tenant.id, outcome="SUCCESS",
            policy_checks=policy_checks_data,
            upstream_response_headers=dict(upstream_response.headers),
            upstream_response_body_preview=body_preview)
        try:
            await self._log.write(log_event)
        except Exception:
            pass

        return GatewayResponse(
            status_code=upstream_response.status_code,
            headers=upstream_response.headers, body=upstream_response.body)

    async def _emit_audit(self, event: AuditEvent) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.write(event)
        except Exception:
            pass
