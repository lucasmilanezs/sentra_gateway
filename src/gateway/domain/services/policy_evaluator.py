from typing import Optional

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request


class PolicyEvaluator:
    """
    Domain service that evaluates whether a request satisfies a route's policy.

    Pure business logic — no I/O, no framework dependencies.
    Each check is applied in order; the first failure short-circuits evaluation.

    Routes with no associated policy pass all requests through (open by default).
    This default is intentional for the prototype: routes must be explicitly
    secured, which keeps the developer experience simple while the admin plane
    policy CRUD is being built.
    """

    def evaluate(self, policy: Optional[Policy], request: Request) -> PolicyResult:
        if policy is None:
            return PolicyResult(allowed=True)

        if policy.requires_auth:
            result = self._check_auth(request)
            if not result.allowed:
                return result

        return PolicyResult(allowed=True)

    def _check_auth(self, request: Request) -> PolicyResult:
        """
        Verifies that a Bearer token is present in the Authorization header.

        Full JWT signature and claims validation (RFC 7519) will be performed
        by the JwtValidator service once the admin plane provides signing keys.
        At this stage we enforce the presence and format of the header.
        """
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return PolicyResult(
                allowed=False,
                status_code=401,
                reason="Missing or malformed Authorization header. Expected: Bearer <token>.",
            )
        return PolicyResult(allowed=True)
