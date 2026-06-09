from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class SecretCipherError(RuntimeError):
    """Raised when policy signing material cannot be encrypted or decrypted."""


@dataclass(frozen=True)
class SecretCipher:
    """Small infrastructure helper for reversible encryption of tenant-provided secrets.

    The key must be supplied by local environment and must never be versioned.
    """

    key: str

    def __post_init__(self) -> None:
        if not self.key:
            raise SecretCipherError("SENTRA_POLICY_SECRET_KEY is required to store JWT signing material.")
        try:
            Fernet(self.key.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive, depends on cryptography internals
            raise SecretCipherError("SENTRA_POLICY_SECRET_KEY must be a valid Fernet key.") from exc

    @classmethod
    def optional(cls, key: Optional[str]) -> "SecretCipher | None":
        if not key:
            return None
        return cls(key=key)

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")

    def encrypt(self, value: str) -> str:
        if not value:
            raise SecretCipherError("Cannot encrypt an empty secret.")
        return Fernet(self.key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        if not value:
            raise SecretCipherError("Cannot decrypt an empty secret.")
        try:
            return Fernet(self.key.encode("utf-8")).decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretCipherError("Stored policy signing material cannot be decrypted with the configured key.") from exc


def secret_hint(value: str) -> str:
    """Return a non-sensitive hint for UI/audit. Never returns the full secret."""
    if not value:
        return ""
    stripped = value.strip()
    if len(stripped) <= 4:
        return "configured"
    return stripped[-4:]
