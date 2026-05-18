import time
from typing import Any, Optional

from jose import JWTError, jwt

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request


class PolicyEvaluator:
    """
    Evaluates authentication requirements and structural JWT rules on a policy.
    """

    def __init__(self, jwt_secret: Optional[str] = None, jwt_algorithms: tuple[str, ...] = ("HS256",)) -> None:
        self._jwt_secret = jwt_secret
        self._jwt_algorithms = jwt_algorithms

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

        token = auth[7:].strip()
        if not token or token.count(".") != 2:
            return PolicyResult(
                allowed=False,
                status_code=401,
                reason="Invalid JWT format. Expected three Base64url segments.",
            )

        try:
            if self._jwt_secret:
                payload = jwt.decode(
                    token,
                    self._jwt_secret,
                    algorithms=list(self._jwt_algorithms),
                    options={"verify_aud": bool(policy.jwt_audience)},
                    audience=policy.jwt_audience,
                    issuer=policy.jwt_issuer,
                )
            else:
                payload = jwt.get_unverified_claims(token)
                header = jwt.get_unverified_header(token)
                alg = header.get("alg")
                if alg in (None, "none"):
                    return PolicyResult(
                        allowed=False,
                        status_code=401,
                        reason="JWT algorithm 'none' is not allowed.",
                    )
                if policy.jwt_validate_exp:
                    self._validate_exp(payload, policy.jwt_clock_skew_seconds)
                if policy.jwt_issuer and payload.get("iss") != policy.jwt_issuer:
                    return PolicyResult(
                        allowed=False,
                        status_code=401,
                        reason="JWT issuer claim does not match policy.",
                    )
                if policy.jwt_audience:
                    aud = payload.get("aud")
                    if isinstance(aud, list):
                        if policy.jwt_audience not in aud:
                            return PolicyResult(
                                allowed=False,
                                status_code=401,
                                reason="JWT audience claim does not match policy.",
                            )
                    elif aud != policy.jwt_audience:
                        return PolicyResult(
                            allowed=False,
                            status_code=401,
                            reason="JWT audience claim does not match policy.",
                        )
        except JWTError as exc:
            return PolicyResult(
                allowed=False,
                status_code=401,
                reason=f"JWT validation failed: {exc}",
            )

        if policy.allowed_roles:
            role = payload.get("role") if isinstance(payload, dict) else None
            if role not in policy.allowed_roles:
                return PolicyResult(
                    allowed=False,
                    status_code=403,
                    reason="Role not permitted for this route.",
                )

        return PolicyResult(allowed=True)

    @staticmethod
    def _validate_exp(payload: dict[str, Any], skew_seconds: int) -> None:
        exp = payload.get("exp")
        if exp is None:
            raise JWTError("JWT missing exp claim.")
        now = time.time()
        if float(exp) < now - skew_seconds:
            raise JWTError("JWT has expired.")
