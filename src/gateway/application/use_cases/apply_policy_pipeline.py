from typing import Optional

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker


class ApplyPolicyPipeline:
    """
    Application use case that orchestrates policy enforcement.

    Sequences domain service calls in the correct order — first
    authentication, then rate limiting, then RBAC (planned).
    Each check short-circuits evaluation on failure.

    Contains no business logic — delegates every decision to domain
    services. Orchestration only.

    RateLimitChecker is optional: when absent (e.g. in test environments
    without Redis), rate limiting is silently skipped.
    """

    def __init__(
        self,
        policy_evaluator: PolicyEvaluator,
        rate_limit_checker: Optional[RateLimitChecker] = None,
    ) -> None:
        self._evaluator = policy_evaluator
        self._rate_limit = rate_limit_checker

    async def apply(self, policy: Optional[Policy], request: Request) -> PolicyResult:
        if policy is None:
            return PolicyResult(allowed=True)

        # 1. Authentication
        result = self._evaluator.evaluate(policy, request)
        if not result.allowed:
            return result

        # 2. Rate limiting
        if self._rate_limit is not None:
            result = await self._rate_limit.check(policy, request)
            if not result.allowed:
                return result

        # 3. RBAC — planned, checker will be injected here

        return PolicyResult(allowed=True)