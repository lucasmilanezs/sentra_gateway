from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.ports.tenant_repository import TenantRepositoryPort
from src.admin.infrastructure.persistence.json.store import (
    DocumentStore,
    _parse_dt,
    _serialize_dt,
)


def _row_to_tenant(row: dict) -> Tenant:
    return Tenant(
        id=row["id"],
        name=row["name"],
        alias=row["alias"],
        domain=row.get("domain"),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _tenant_to_row(t: Tenant) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "alias": t.alias,
        "domain": t.domain,
        "created_at": _serialize_dt(t.created_at),
        "updated_at": _serialize_dt(t.updated_at),
    }


class TenantRepository(TenantRepositoryPort):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def list_all(self) -> list[Tenant]:
        doc = await self._store.read_async()
        return [_row_to_tenant(r) for r in doc["tenants"]]

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        doc = await self._store.read_async()
        for r in doc["tenants"]:
            if r["id"] == tenant_id:
                return _row_to_tenant(r)
        return None

    async def get_by_alias(self, alias: str) -> Tenant | None:
        doc = await self._store.read_async()
        for r in doc["tenants"]:
            if r["alias"] == alias:
                return _row_to_tenant(r)
        return None

    async def save(self, tenant: Tenant) -> None:
        row = _tenant_to_row(tenant)

        def mut(doc: dict) -> None:
            tenants = doc["tenants"]
            for i, r in enumerate(tenants):
                if r["id"] == tenant.id:
                    tenants[i] = row
                    return
            tenants.append(row)

        await self._store.mutate_async(mut)

    async def delete(self, tenant_id: str) -> bool:
        removed = False

        def mut(doc: dict) -> None:
            nonlocal removed
            before = len(doc["tenants"])
            doc["tenants"] = [r for r in doc["tenants"] if r["id"] != tenant_id]
            removed = len(doc["tenants"]) < before

        await self._store.mutate_async(mut)
        return removed