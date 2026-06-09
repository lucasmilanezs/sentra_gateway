from src.admin.domain.entities.user import User
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.infrastructure.persistence.json.store import (
    DocumentStore,
    _parse_dt,
    _serialize_dt,
)


def _row_to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        tenant_id=row.get("tenant_id"),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
        role=row.get("role", "admin"),
        permissions=row.get("permissions") or [],
    )


def _user_to_row(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "password_hash": u.password_hash,
        "tenant_id": u.tenant_id,
        "role": u.role,
        "permissions": list(u.permissions),
        "created_at": _serialize_dt(u.created_at),
        "updated_at": _serialize_dt(u.updated_at),
    }


class UserRepository(UserRepositoryPort):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def get_by_id(self, user_id: str) -> User | None:
        doc = await self._store.read_async()
        for r in doc["users"]:
            if r["id"] == user_id:
                return _row_to_user(r)
        return None

    async def get_by_email(self, email: str) -> User | None:
        doc = await self._store.read_async()
        for r in doc["users"]:
            if r["email"] == email:
                return _row_to_user(r)
        return None

    async def save(self, user: User) -> None:
        row = _user_to_row(user)

        def mut(doc: dict) -> None:
            users = doc["users"]
            for i, r in enumerate(users):
                if r["id"] == user.id:
                    users[i] = row
                    return
            users.append(row)

        await self._store.mutate_async(mut)

    async def list_members_by_tenant(self, tenant_id: str) -> list[User]:
        doc = await self._store.read_async()
        return [
            _row_to_user(r)
            for r in doc["users"]
            if r.get("tenant_id") == tenant_id and r.get("role", "admin") == "member"
        ]

    async def delete(self, user_id: str) -> bool:
        deleted = False

        def mut(doc: dict) -> None:
            nonlocal deleted
            original = len(doc["users"])
            doc["users"] = [r for r in doc["users"] if r.get("id") != user_id]
            deleted = len(doc["users"]) != original

        await self._store.mutate_async(mut)
        return deleted
