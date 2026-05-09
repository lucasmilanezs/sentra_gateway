from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request


class PolicyEvaluator:
    """
    Domain service that evaluates authentication requirements of a policy.

    Single responsibility: checks whether the request satisfies the
    authentication rule defined in the policy. Does not orchestrate
    other checks — that is the pipeline's job.

    Full JWT signature and claims validation (RFC 7519) will replace
    the current Bearer-presence check once signing keys are provisioned
    via the admin policy configuration.
    """

    def evaluate(self, policy: Policy, request: Request) -> PolicyResult:
        if not policy.requires_auth:
            return PolicyResult(allowed=True)

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return PolicyResult(
                allowed=False,
                status_code=401,
                reason="Missing or malformed Authorization header. Expected: Bearer <token>.",
            )
        return PolicyResult(allowed=True)