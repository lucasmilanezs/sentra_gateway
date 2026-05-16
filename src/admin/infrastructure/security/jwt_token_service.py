from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.admin.domain.exceptions import AuthError
from src.admin.domain.services.token_service import TokenServicePort
from src.admin.domain.value_objects.jwt_claims import JwtClaims


class JwtTokenService(TokenServicePort):
    def __init__(self, secret: str, algorithm: str, expire_minutes: int) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_access_token(
        self,
        user_id: str,
        email: str,
        tenant_id: str | None,
        role: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self._expire_minutes)
        payload: dict = {
            "sub": user_id,
            "email": email,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if role is not None:
            payload["role"] = role
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_and_validate(self, token: str) -> JwtClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as e:
            raise AuthError("token inválido ou expirado") from e
        sub = payload.get("sub")
        email = payload.get("email")
        if not sub or not email:
            raise AuthError("token inválido")
        tenant_id = payload.get("tenant_id")
        role = payload.get("role")
        return JwtClaims(sub=str(sub), email=str(email), tenant_id=tenant_id, role=role)
