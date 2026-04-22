from src.admin.domain.ports.password_reset_repository import (
    PasswordResetRecord,
    PasswordResetRepositoryPort,
)
from src.admin.infrastructure.persistence.json.store import DocumentStore, _parse_dt, _serialize_dt


class PasswordResetRepository(PasswordResetRepositoryPort):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def save(self, record: PasswordResetRecord) -> None:
        payload = {
            "code_hash": record.code_hash,
            "expires_at": _serialize_dt(record.expires_at),
        }

        def mut(doc: dict) -> None:
            doc["password_resets"][record.email] = payload

        await self._store.mutate_async(mut)

    async def get_for_email(self, email: str) -> PasswordResetRecord | None:
        doc = await self._store.read_async()
        raw = doc["password_resets"].get(email)
        if not raw:
            return None
        return PasswordResetRecord(
            email=email,
            code_hash=raw["code_hash"],
            expires_at=_parse_dt(raw["expires_at"]),
        )

    async def clear(self, email: str) -> None:
        def mut(doc: dict) -> None:
            doc["password_resets"].pop(email, None)

        await self._store.mutate_async(mut)