import bcrypt

from src.admin.domain.services.password_hasher import PasswordHasherPort


class BcryptPasswordHasher(PasswordHasherPort):
    def hash(self, plain_password: str) -> str:
        return bcrypt.hashpw(
            plain_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )