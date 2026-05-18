from typing import Optional

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker


class ApplyPolicyPipeline:
    """
    Orchestrates policy enforcement: authentication → rate limiting → RBAC (in evaluator).
    """

    def __init__(
        self,
        policy_evaluator: PolicyEvaluator,
        rate_limit_checker: Optional[RateLimitChecker] = None,
    ) -> None:
        self._evaluator = policy_evaluator
        self._rate_limit = rate_limit_checker

    async def apply(
        self,
        policy: Optional[Policy],
        request: Request,
        *,
        tenant_id: str,
        route_id: str,
    ) -> PolicyResult:
        if policy is None:
            return PolicyResult(allowed=True)

        result = self._evaluator.evaluate(policy, request)
        if not result.allowed:
            return result

        if self._rate_limit is not None:
            result = await self._rate_limit.check(
                policy, request, tenant_id=tenant_id, route_id=route_id
            )
            if not result.allowed:
                return result

        return PolicyResult(allowed=True)
