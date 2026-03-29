from abc import ABC, abstractmethod

from src.admin.domain.value_objects.jwt_claims import JwtClaims


class TokenServicePort(ABC):
    @abstractmethod
    def create_access_token(self, user_id: str, email: str, tenant_id: str | None) -> str:
        ...

    @abstractmethod
    def decode_and_validate(self, token: str) -> JwtClaims:
        ...
