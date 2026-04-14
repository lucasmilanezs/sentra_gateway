from typing import Dict, Optional

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.ports.policy_repository import PolicyRepository


_DEFAULT_POLICIES: Dict[str, Policy] = {
    # No policies by default — all routes are open.
    # Add entries keyed by route_id to enforce auth, rate limiting, etc.
    # Example:
    #   "route-httpbin": Policy(
    #       id="policy-httpbin",
    #       route_id="route-httpbin",
    #       requires_auth=True,
    #   ),
}


class InMemoryPolicyRepository(PolicyRepository):
    """
    In-memory policy store for local development and testing.

    Returning None for a route means no policy is configured,
    and PolicyEvaluator will allow all requests through.

    Replace with a CachedPolicyRepository (Redis snapshot) or
    PostgresPolicyRepository for production.
    """

    def __init__(self, policies: Optional[Dict[str, Policy]] = None) -> None:
        self._policies = policies if policies is not None else dict(_DEFAULT_POLICIES)

    async def get_by_route_id(self, route_id: str) -> Optional[Policy]:
        return self._policies.get(route_id)
