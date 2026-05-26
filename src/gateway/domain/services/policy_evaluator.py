import time
from typing import Any, List, Optional

from jose import JWTError, jwt

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyEvaluationDetail, PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_components import DEFAULT_POLICY_COMPONENTS, PolicyComponent


class PolicyEvaluator:

    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        jwt_algorithms: tuple[str, ...] = ("HS256",),
        policy_components: tuple[PolicyComponent, ...] = DEFAULT_POLICY_COMPONENTS,
    ) -> None:
        self._jwt_secret = jwt_secret
        self._jwt_algorithms = jwt_algorithms
        self._policy_components = policy_components

    def evaluate(self, policy: Policy, request: Request) -> PolicyResult:
        checks: List[PolicyEvaluationDetail] = []

        if not policy.requires_auth:
            checks.append(PolicyEvaluationDetail(check="requires_auth", passed=True, detail="auth not required"))
        else:
            auth_result = self._evaluate_auth(policy, request)
            checks.extend(auth_result.checks)
            if not auth_result.allowed:
                return PolicyResult(allowed=False, status_code=auth_result.status_code, reason=auth_result.reason, checks=tuple(checks))

        for component in self._policy_components:
            if not component.is_enabled(policy):
                continue
            detail = component.evaluate(policy, request)
            checks.append(detail)
            if not detail.passed:
                return PolicyResult(allowed=False, status_code=400, reason=detail.detail, checks=tuple(checks))

        return PolicyResult(allowed=True, checks=tuple(checks))

    def _evaluate_auth(self, policy: Policy, request: Request) -> PolicyResult:
        checks: List[PolicyEvaluationDetail] = []
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            checks.append(PolicyEvaluationDetail(check="bearer_token", passed=False, detail="Missing Authorization header."))
            return PolicyResult(allowed=False, status_code=401, reason="Missing or malformed Authorization header. Expected: Bearer <token>.", checks=tuple(checks))

        token = auth[7:].strip()
        if not token or token.count(".") != 2:
            checks.append(PolicyEvaluationDetail(check="jwt_format", passed=False, detail="Invalid JWT format."))
            return PolicyResult(allowed=False, status_code=401, reason="Invalid JWT format. Expected three Base64url segments.", checks=tuple(checks))

        payload: dict = {}
        try:
            if self._jwt_secret:
                payload = jwt.decode(token, self._jwt_secret, algorithms=list(self._jwt_algorithms),
                    options={"verify_aud": bool(policy.jwt_audience)}, audience=policy.jwt_audience, issuer=policy.jwt_issuer)
                checks.append(PolicyEvaluationDetail(check="jwt_signature", passed=True, detail="Signature verified."))
            else:
                payload = jwt.get_unverified_claims(token)
                header = jwt.get_unverified_header(token)
                alg = header.get("alg")
                if alg in (None, "none"):
                    checks.append(PolicyEvaluationDetail(check="jwt_algorithm", passed=False, detail="Algorithm 'none' not allowed."))
                    return PolicyResult(allowed=False, status_code=401, reason="JWT algorithm 'none' is not allowed.", checks=tuple(checks))
                checks.append(PolicyEvaluationDetail(check="jwt_algorithm", passed=True, detail=f"Algorithm: {alg}"))
                if policy.jwt_validate_exp:
                    self._validate_exp(payload, policy.jwt_clock_skew_seconds)
                    checks.append(PolicyEvaluationDetail(check="jwt_exp", passed=True, detail="Expiration valid."))
                if policy.jwt_issuer and payload.get("iss") != policy.jwt_issuer:
                    checks.append(PolicyEvaluationDetail(check="jwt_issuer", passed=False, detail=f"Expected '{policy.jwt_issuer}', got '{payload.get('iss')}'."))
                    return PolicyResult(allowed=False, status_code=401, reason="JWT issuer claim does not match policy.", checks=tuple(checks))
                if policy.jwt_issuer:
                    checks.append(PolicyEvaluationDetail(check="jwt_issuer", passed=True, detail=f"Issuer matches: {policy.jwt_issuer}"))
                if policy.jwt_audience:
                    aud = payload.get("aud")
                    aud_ok = (isinstance(aud, list) and policy.jwt_audience in aud) or aud == policy.jwt_audience
                    if not aud_ok:
                        checks.append(PolicyEvaluationDetail(check="jwt_audience", passed=False, detail=f"Expected '{policy.jwt_audience}', got '{aud}'."))
                        return PolicyResult(allowed=False, status_code=401, reason="JWT audience claim does not match policy.", checks=tuple(checks))
                    checks.append(PolicyEvaluationDetail(check="jwt_audience", passed=True, detail=f"Audience matches: {policy.jwt_audience}"))
        except JWTError as exc:
            checks.append(PolicyEvaluationDetail(check="jwt_validation", passed=False, detail=str(exc)))
            return PolicyResult(allowed=False, status_code=401, reason=f"JWT validation failed: {exc}", checks=tuple(checks))

        if policy.allowed_roles:
            role = payload.get("role") if isinstance(payload, dict) else None
            if role not in policy.allowed_roles:
                checks.append(PolicyEvaluationDetail(check="role_authorization", passed=False, detail=f"Role '{role}' not in {policy.allowed_roles}"))
                return PolicyResult(allowed=False, status_code=403, reason="Role not permitted for this route.", checks=tuple(checks))
            checks.append(PolicyEvaluationDetail(check="role_authorization", passed=True, detail=f"Role '{role}' allowed."))

        return PolicyResult(allowed=True, checks=tuple(checks))

    @staticmethod
    def _validate_exp(payload: dict[str, Any], skew_seconds: int) -> None:
        exp = payload.get("exp")
        if exp is None:
            raise JWTError("JWT missing exp claim.")
        if float(exp) < time.time() - skew_seconds:
            raise JWTError("JWT has expired.")
