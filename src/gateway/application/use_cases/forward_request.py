import time

from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.application.ports.gateway_request_port import GatewayRequestPort
from src.gateway.domain.models.request import Request
from src.gateway.domain.ports.domain_repository import DomainRepository
from src.gateway.domain.ports.log_port import LogPort
from src.gateway.domain.ports.policy_repository import PolicyRepository
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.domain.ports.upstream_proxy_port import UpstreamProxyPort
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator


class RouteNotFoundError(Exception):
    """No registered route matched the incoming request path."""


class DomainNotFoundError(Exception):
    """The domain referenced by a matched route is not configured."""


class PolicyDeniedError(Exception):
    """The route policy denied the request."""

    def __init__(self, reason: str, status_code: int = 403) -> None:
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


class ForwardRequest(GatewayRequestPort):
    """
    Core use case of the gateway data plane.

    Orchestrates the full request processing pipeline:
      1. Route resolution — match path against registered routes
      2. Domain resolution — retrieve the backend service for the route
      3. Policy evaluation — apply security controls (auth, rate limit, RBAC)
      4. Request forwarding — proxy the validated request upstream
      5. Log recording — write an operational log event (non-blocking)

    Contains no business logic. All decisions are delegated to domain
    services; all I/O is performed via outbound ports. This makes the
    pipeline independently testable without any infrastructure.
    """

    def __init__(
        self,
        route_repository: RouteRepository,
        domain_repository: DomainRepository,
        policy_repository: PolicyRepository,
        proxy: UpstreamProxyPort,
        log_port: LogPort,
        policy_evaluator: PolicyEvaluator,
        log_event_builder: LogEventBuilder,
    ) -> None:
        self._routes = route_repository
        self._domains = domain_repository
        self._policies = policy_repository
        self._proxy = proxy
        self._log = log_port
        self._policy_evaluator = policy_evaluator
        self._log_event_builder = log_event_builder

    async def handle(self, request: Request, raw_body: bytes) -> GatewayResponse:
        start = time.monotonic()

        # 1. Route resolution
        route = await self._routes.get_by_path(request.path, request.method.value)
        if route is None:
            raise RouteNotFoundError(
                f"No route matched path '{request.path}' [{request.method.value}]."
            )

        # 2. Domain resolution
        domain = await self._domains.get_by_id(route.domain_id)
        if domain is None:
            raise DomainNotFoundError(
                f"Domain '{route.domain_id}' referenced by route '{route.id}' is not configured."
            )

        # 3. Policy evaluation
        policy = await self._policies.get_by_route_id(route.id)
        result = self._policy_evaluator.evaluate(policy, request)
        if not result.allowed:
            raise PolicyDeniedError(
                reason=result.reason or "Request denied by policy.",
                status_code=result.status_code,
            )

        # 4. Forward
        upstream_path = route.strip_prefix(request.path)
        upstream_url = domain.backend_url.build_upstream(upstream_path)

        upstream_response = await self._proxy.forward(
            method=request.method.value,
            url=upstream_url,
            headers=request.headers,
            body=raw_body,
            query_params=request.query_params,
        )

        latency_ms = (time.monotonic() - start) * 1000

        # 5. Log (best-effort — must not affect the response)
        log_event = self._log_event_builder.build(
            request=request,
            upstream_url=upstream_url,
            status_code=upstream_response.status_code,
            latency_ms=latency_ms,
            route_id=route.id,
        )
        try:
            await self._log.write(log_event)
        except Exception:
            pass

        return GatewayResponse(
            status_code=upstream_response.status_code,
            headers=upstream_response.headers,
            body=upstream_response.body,
        )
