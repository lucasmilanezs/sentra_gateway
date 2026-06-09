import time
from typing import Any, List

from jose import JWTError, jwt

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyEvaluationDetail, PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_components import DEFAULT_POLICY_COMPONENTS, PolicyComponent


class PolicyEvaluator:
    """Evaluates gateway policies without managing contractor sessions.

    The gateway can pre-filter token presence/shape/declared claims and, when
    explicitly configured, verify a JWT signature with contractor-provided
    signing material. Fine-grained authorization, revocation and session state
    remain responsibility of the protected backend.
    """

    def __init__(
        self,
        policy_components: tuple[PolicyComponent, ...] = DEFAULT_POLICY_COMPONENTS,
    ) -> None:
        self._policy_components = policy_components

    def evaluate(self, policy: Policy, request: Request) -> PolicyResult:
        checks: List[PolicyEvaluationDetail] = []

        auth_result = self._evaluate_auth(policy, request)
        checks.extend(auth_result.checks)
        if not auth_result.allowed:
            return PolicyResult(
                allowed=False,
                status_code=auth_result.status_code,
                reason=auth_result.reason,
                checks=tuple(checks),
            )

        for component in self._policy_components:
            if not component.is_enabled(policy):
                continue
            detail = component.evaluate(policy, request)
            checks.append(detail)
            if not detail.passed:
                return PolicyResult(allowed=False, status_code=400, reason=detail.detail, checks=tuple(checks))

        return PolicyResult(allowed=True, checks=tuple(checks))

    def _evaluate_auth(self, policy: Policy, request: Request) -> PolicyResult:
        mode = policy.auth_mode or Policy.AUTH_NONE
        checks: List[PolicyEvaluationDetail] = []

        if mode == Policy.AUTH_NONE:
            checks.append(PolicyEvaluationDetail(check="auth_mode", passed=True, detail="Token validation disabled."))
            return PolicyResult(allowed=True, checks=tuple(checks))

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            checks.append(PolicyEvaluationDetail(check="bearer_token", passed=False, detail="Missing Authorization header."))
            return PolicyResult(
                allowed=False,
                status_code=401,
                reason="Missing or malformed Authorization header. Expected: Bearer <token>.",
                checks=tuple(checks),
            )

        token = auth[7:].strip()
        if not token:
            checks.append(PolicyEvaluationDetail(check="bearer_token", passed=False, detail="Empty bearer token."))
            return PolicyResult(allowed=False, status_code=401, reason="Empty bearer token.", checks=tuple(checks))

        checks.append(PolicyEvaluationDetail(check="bearer_token", passed=True, detail="Bearer token present."))

        if mode == Policy.AUTH_BEARER:
            return PolicyResult(allowed=True, checks=tuple(checks))

        structural, payload = self._decode_unverified_jwt(token)
        checks.extend(structural.checks)
        if not structural.allowed:
            return PolicyResult(allowed=False, status_code=structural.status_code, reason=structural.reason, checks=tuple(checks))


        if mode == Policy.AUTH_JWT_STRUCTURAL:
            return PolicyResult(allowed=True, checks=tuple(checks))

        if mode == Policy.AUTH_JWT_CLAIMS:
            claims_result = self._evaluate_declared_claims(policy, payload)
            checks.extend(claims_result.checks)
            return PolicyResult(
                allowed=claims_result.allowed,
                status_code=claims_result.status_code,
                reason=claims_result.reason,
                checks=tuple(checks),
            )

        if mode == Policy.AUTH_JWT_SIGNED:
            signed_result = self._evaluate_signed_jwt(policy, token)
            checks.extend(signed_result.checks)
            return PolicyResult(
                allowed=signed_result.allowed,
                status_code=signed_result.status_code,
                reason=signed_result.reason,
                checks=tuple(checks),
            )

        checks.append(PolicyEvaluationDetail(check="auth_mode", passed=False, detail=f"Unsupported auth mode: {mode}"))
        return PolicyResult(allowed=False, status_code=500, reason="Unsupported gateway auth mode.", checks=tuple(checks))

    def _decode_unverified_jwt(self, token: str) -> tuple[PolicyResult, dict[str, Any]]:
        checks: List[PolicyEvaluationDetail] = []
        if token.count(".") != 2:
            checks.append(PolicyEvaluationDetail(check="jwt_format", passed=False, detail="Invalid JWT format."))
            return PolicyResult(allowed=False, status_code=401, reason="Invalid JWT format. Expected three Base64url segments.", checks=tuple(checks)), {}
        try:
            header = jwt.get_unverified_header(token)
            payload = jwt.get_unverified_claims(token)
        except JWTError as exc:
            checks.append(PolicyEvaluationDetail(check="jwt_structure", passed=False, detail=str(exc)))
            return PolicyResult(allowed=False, status_code=401, reason="Invalid JWT structure.", checks=tuple(checks)), {}

        alg = header.get("alg")
        if not alg or str(alg).lower() == "none":
            checks.append(PolicyEvaluationDetail(check="jwt_algorithm", passed=False, detail="Algorithm 'none' not allowed."))
            return PolicyResult(allowed=False, status_code=401, reason="JWT algorithm 'none' is not allowed.", checks=tuple(checks)), {}

        checks.append(PolicyEvaluationDetail(check="jwt_structure", passed=True, detail="JWT header and payload are readable."))
        checks.append(PolicyEvaluationDetail(check="jwt_algorithm", passed=True, detail=f"Declared algorithm: {alg}"))

        return PolicyResult(allowed=True, checks=tuple(checks)), payload

    def _evaluate_declared_claims(self, policy: Policy, payload: dict[str, Any]) -> PolicyResult:
        checks: List[PolicyEvaluationDetail] = []
        try:
            if policy.jwt_validate_exp:
                self._validate_exp(payload, policy.jwt_clock_skew_seconds)
                checks.append(PolicyEvaluationDetail(check="jwt_exp", passed=True, detail="Declared expiration is not expired."))
            else:
                checks.append(PolicyEvaluationDetail(check="jwt_exp", passed=True, detail="Expiration pre-check disabled."))

            if policy.jwt_issuer:
                if payload.get("iss") != policy.jwt_issuer:
                    checks.append(PolicyEvaluationDetail(check="jwt_issuer", passed=False, detail="Declared issuer does not match policy."))
                    return PolicyResult(allowed=False, status_code=401, reason="JWT issuer claim does not match policy.", checks=tuple(checks))
                checks.append(PolicyEvaluationDetail(check="jwt_issuer", passed=True, detail="Declared issuer matches policy."))

            if policy.jwt_audience:
                aud = payload.get("aud")
                audiences = aud if isinstance(aud, list) else [aud]
                if policy.jwt_audience not in audiences:
                    checks.append(PolicyEvaluationDetail(check="jwt_audience", passed=False, detail="Declared audience does not match policy."))
                    return PolicyResult(allowed=False, status_code=401, reason="JWT audience claim does not match policy.", checks=tuple(checks))
                checks.append(PolicyEvaluationDetail(check="jwt_audience", passed=True, detail="Declared audience matches policy."))
        except JWTError as exc:
            checks.append(PolicyEvaluationDetail(check="jwt_claims", passed=False, detail=str(exc)))
            return PolicyResult(allowed=False, status_code=401, reason=str(exc), checks=tuple(checks))

        return PolicyResult(allowed=True, checks=tuple(checks))

    def _evaluate_signed_jwt(self, policy: Policy, token: str) -> PolicyResult:
        checks: List[PolicyEvaluationDetail] = []

        if not policy.jwt_signing_key:
            checks.append(PolicyEvaluationDetail(check="jwt_signature", passed=False, detail="Signing material is not configured or unavailable."))
            return PolicyResult(allowed=False, status_code=503, reason="JWT signature validation is configured, but signing material is unavailable.", checks=tuple(checks))

        algorithm = policy.jwt_signing_algorithm or "HS256"
        try:
            jwt.decode(
                token,
                policy.jwt_signing_key,
                algorithms=[algorithm],
                audience=policy.jwt_audience,
                issuer=policy.jwt_issuer,
                options={
                    "verify_aud": bool(policy.jwt_audience),
                    "verify_exp": bool(policy.jwt_validate_exp),
                    "leeway": int(policy.jwt_clock_skew_seconds or 0),
                },
            )
        except JWTError as exc:
            checks.append(PolicyEvaluationDetail(check="jwt_signature", passed=False, detail=str(exc)))
            return PolicyResult(allowed=False, status_code=401, reason="JWT signature validation failed.", checks=tuple(checks))

        checks.append(PolicyEvaluationDetail(check="jwt_signature", passed=True, detail=f"Signature verified with {algorithm}."))
        if policy.jwt_validate_exp:
            checks.append(PolicyEvaluationDetail(check="jwt_exp", passed=True, detail="Signed expiration claim is valid."))
        if policy.jwt_issuer:
            checks.append(PolicyEvaluationDetail(check="jwt_issuer", passed=True, detail="Signed issuer claim matches policy."))
        if policy.jwt_audience:
            checks.append(PolicyEvaluationDetail(check="jwt_audience", passed=True, detail="Signed audience claim matches policy."))
        return PolicyResult(allowed=True, checks=tuple(checks))

    def _validate_exp(self, payload: dict[str, Any], skew_seconds: int) -> None:
        exp = payload.get("exp")
        if exp is None:
            raise JWTError("JWT missing exp claim.")
        try:
            exp_value = float(exp)
        except (TypeError, ValueError) as exc:
            raise JWTError("JWT exp claim must be numeric.") from exc
        if exp_value < time.time() - skew_seconds:
            raise JWTError("JWT has expired.")
