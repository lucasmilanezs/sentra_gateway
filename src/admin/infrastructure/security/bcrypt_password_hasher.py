from passlib.context import CryptContext

from src.admin.domain.services.password_hasher import PasswordHasherPort


class BcryptPasswordHasher(PasswordHasherPort):
    def __init__(self) -> None:
        self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain_password: str) -> str:
        return self._ctx.hash(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return self._ctx.verify(plain_password, password_hash)
