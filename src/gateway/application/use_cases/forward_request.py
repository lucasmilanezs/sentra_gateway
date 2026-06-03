import asyncio
import logging
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
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.ports.audit_port import AuditPort
from src.gateway.domain.ports.domain_repository import DomainRepository
from src.gateway.domain.ports.log_port import LogPort
from src.gateway.domain.ports.policy_repository import PolicyRepository
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.domain.ports.upstream_proxy_port import UpstreamProxyPort
from src.gateway.domain.services.audit_event_builder import AuditEventBuilder
from src.gateway.domain.services.log_event_builder import LogEventBuilder

logger = logging.getLogger(__name__)

# Backward-compat re-exports so nothing outside breaks
__all__ = [
    "TenantNotFoundError", "RouteNotFoundError",
    "DomainNotFoundError", "PolicyDeniedError", "ForwardRequest",
]


class ForwardRequest(GatewayRequestPort):
    """Gateway use case: orchestrates request resolution, policy enforcement and proxying."""

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
        tenant = None
        route = None
        domain = None
        upstream_url = ""
        policy_result: PolicyResult | None = None

        try:
            tenant = await self._tenants.get_by_domain(request.host)
            if tenant is None:
                latency_ms = self._elapsed(start)
                self._schedule_audit(self._audit_builder.build_resolution_failure(
                    request=request, outcome="TENANT_NOT_FOUND", latency_ms=latency_ms,
                ))
                self._schedule_log(
                    request=request, upstream_url="", status_code=404, latency_ms=latency_ms,
                    outcome="TENANT_NOT_FOUND", error=f"No tenant registered for host '{request.host}'.",
                    layer_errors={"domain": "TENANT_NOT_FOUND", "http": "404"},
                )
                raise TenantNotFoundError(f"No tenant registered for host '{request.host}'.")

            route = await self._routes.get_by_path(request.path, request.method.value, tenant.id)
            if route is None:
                latency_ms = self._elapsed(start)
                self._schedule_audit(self._audit_builder.build_resolution_failure(
                    request=request, outcome="ROUTE_NOT_FOUND", tenant_id=tenant.id, latency_ms=latency_ms,
                ))
                self._schedule_log(
                    request=request, upstream_url="", status_code=404, latency_ms=latency_ms,
                    tenant_id=tenant.id, outcome="ROUTE_NOT_FOUND",
                    error=f"No route matched path '{request.path}' [{request.method.value}].",
                    layer_errors={"domain": "ROUTE_NOT_FOUND", "http": "404"},
                )
                raise RouteNotFoundError(f"No route matched path '{request.path}' [{request.method.value}].")

            domain = await self._domains.get_by_id(route.domain_id)
            if domain is None:
                latency_ms = self._elapsed(start)
                self._schedule_audit(self._audit_builder.build_resolution_failure(
                    request=request, outcome="DOMAIN_NOT_FOUND", tenant_id=tenant.id, route_id=route.id,
                    latency_ms=latency_ms,
                ))
                self._schedule_log(
                    request=request, upstream_url="", status_code=502, latency_ms=latency_ms,
                    tenant_id=tenant.id, route_id=route.id, outcome="DOMAIN_NOT_FOUND",
                    error=f"Domain '{route.domain_id}' referenced by route '{route.id}' is not configured.",
                    layer_errors={"domain": "DOMAIN_NOT_FOUND", "http": "502"},
                )
                raise DomainNotFoundError(f"Domain '{route.domain_id}' referenced by route '{route.id}' is not configured.")

            policy = await self._policies.get_by_route_id(route.id)
            if policy is None and hasattr(self._policies, "get_domain_policy"):
                policy = self._policies.get_domain_policy(request.host)

            policy_result = await self._pipeline.apply(policy, request, tenant_id=tenant.id, route_id=route.id)
            if not policy_result.allowed:
                latency_ms = self._elapsed(start)
                self._schedule_audit(self._audit_builder.build_policy_denial(
                    request=request, tenant_id=tenant.id, route_id=route.id,
                    policy_result=policy_result, latency_ms=latency_ms,
                ))
                self._schedule_log(
                    request=request, upstream_url="", status_code=policy_result.status_code,
                    latency_ms=latency_ms, tenant_id=tenant.id, route_id=route.id,
                    outcome="POLICY_DENIED", error=policy_result.reason,
                    policy_result=policy_result,
                    layer_errors={"domain": "POLICY_DENIED", "http": str(policy_result.status_code)},
                )
                raise PolicyDeniedError(reason=policy_result.reason or "Request denied by policy.", status_code=policy_result.status_code)

            upstream_path = route.strip_prefix(request.path)
            upstream_url = domain.backend_url.build_upstream(upstream_path)

            try:
                upstream_response = await self._proxy.forward(
                    method=request.method.value, url=upstream_url,
                    headers=request.headers, body=raw_body, query_params=request.query_params)
            except UpstreamError as exc:
                latency_ms = self._elapsed(start)
                self._schedule_audit(self._audit_builder.build_upstream_failure(
                    request=request, tenant_id=tenant.id, route_id=route.id,
                    upstream_url=upstream_url, error_type=exc.error_type,
                    error_message=str(exc), latency_ms=latency_ms))
                self._schedule_log(
                    request=request, upstream_url=upstream_url, status_code=502,
                    latency_ms=latency_ms, tenant_id=tenant.id, route_id=route.id,
                    outcome=exc.error_type, error=str(exc), policy_result=policy_result,
                    layer_errors={"infrastructure": exc.error_type, "http": "502"},
                )
                raise

            latency_ms = self._elapsed(start)
            self._schedule_audit(self._audit_builder.build_success(
                request=request, tenant_id=tenant.id, route_id=route.id,
                upstream_url=upstream_url, upstream_status_code=upstream_response.status_code,
                latency_ms=latency_ms))

            self._schedule_log(
                request=request, upstream_url=upstream_url,
                status_code=upstream_response.status_code, latency_ms=latency_ms,
                route_id=route.id, tenant_id=tenant.id, outcome="SUCCESS",
                policy_result=policy_result,
                upstream_response_headers=dict(upstream_response.headers),
                upstream_response_body=upstream_response.body,
            )

            return GatewayResponse(
                status_code=upstream_response.status_code,
                headers=upstream_response.headers, body=upstream_response.body)

        except (TenantNotFoundError, RouteNotFoundError, DomainNotFoundError, PolicyDeniedError, UpstreamError):
            raise
        except Exception as exc:
            latency_ms = self._elapsed(start)
            tenant_id = getattr(tenant, "id", None)
            route_id = getattr(route, "id", None)
            self._schedule_audit(self._audit_builder.build_unexpected_failure(
                request=request, tenant_id=tenant_id, route_id=route_id,
                upstream_url=upstream_url, error_message=str(exc), latency_ms=latency_ms,
            ))
            self._schedule_log(
                request=request, upstream_url=upstream_url, status_code=502,
                latency_ms=latency_ms, tenant_id=tenant_id, route_id=route_id,
                outcome="UNEXPECTED_ERROR", error=str(exc), policy_result=policy_result,
                layer_errors={"application": type(exc).__name__, "http": "502"},
            )
            raise

    def _schedule_audit(self, event: AuditEvent) -> None:
        if self._audit is None:
            return
        asyncio.create_task(self._safe_audit_write(event))

    async def _safe_audit_write(self, event: AuditEvent) -> None:
        try:
            await self._audit.write(event)
        except Exception as exc:
            logger.warning(
                "Failed to persist gateway audit event [%s]: %s",
                type(exc).__name__,
                exc,
            )

    def _schedule_log(
        self, *, request: Request, upstream_url: str, status_code: int, latency_ms: float,
        route_id: Optional[str] = None, tenant_id: Optional[str] = None,
        error: Optional[str] = None, outcome: str = "SUCCESS",
        policy_result: PolicyResult | None = None,
        upstream_response_headers: Optional[dict[str, str]] = None,
        upstream_response_body: bytes | None = None,
        layer_errors: Optional[dict[str, str]] = None,
    ) -> None:
        event = self._log_event_builder.build(
            request=request, upstream_url=upstream_url, status_code=status_code,
            latency_ms=latency_ms, route_id=route_id, tenant_id=tenant_id,
            error=error, outcome=outcome, policy_result=policy_result,
            upstream_response_headers=upstream_response_headers or {},
            upstream_response_body=upstream_response_body,
            layer_errors=layer_errors or {},
        )
        asyncio.create_task(self._safe_log_write(event))

    async def _safe_log_write(self, event) -> None:
        try:
            await self._log.write(event)
        except Exception as exc:
            logger.warning(
                "Failed to persist gateway operational log [%s]: %s",
                type(exc).__name__,
                exc,
            )

    @staticmethod
    def _elapsed(start: float) -> float:
        return (time.monotonic() - start) * 1000

