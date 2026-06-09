from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.ports.rate_limit import RateLimitPort


class RateLimitChecker:
    """
    Domain service that enforces rate limiting per route and client.

    Key is scoped per tenant + route + client IP so domain-policy fallbacks
    do not share counters across different routes.
    """

    def __init__(self, port: RateLimitPort) -> None:
        self._port = port

    async def check(
        self,
        policy: Policy,
        request: Request,
        *,
        tenant_id: str,
        route_id: str,
    ) -> PolicyResult:
        if policy.rate_limit_per_minute is None:
            return PolicyResult(allowed=True)

        client_ip = (
            request.headers.get("x-forwarded-for")
            or request.headers.get("x-real-ip")
            or "unknown"
        )
        client_ip = client_ip.split(",")[0].strip()

        allowed = await self._port.is_allowed(
            tenant_id=tenant_id,
            route_id=route_id,
            client_ip=client_ip,
            limit=policy.rate_limit_per_minute,
            window_seconds=60,
        )

        if not allowed:
            return PolicyResult(
                allowed=False,
                status_code=429,
                reason=f"Rate limit exceeded. Max {policy.rate_limit_per_minute} requests/min.",
            )

        return PolicyResult(allowed=True)
