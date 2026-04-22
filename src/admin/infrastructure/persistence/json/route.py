from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.value_objects.http_method import HttpMethod
from src.admin.infrastructure.persistence.json.store import (
    DocumentStore,
    _parse_dt,
    _serialize_dt,
)


def _row_to_route(row: dict) -> AdminRoute:
    return AdminRoute(
        id=row["id"],
        tenant_id=row["tenant_id"],
        path_pattern=row["path_pattern"],
        method=HttpMethod(row["method"]),
        backend_url=row["backend_url"],
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _route_to_row(r: AdminRoute) -> dict:
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "path_pattern": r.path_pattern,
        "method": r.method.value,
        "backend_url": r.backend_url,
        "created_at": _serialize_dt(r.created_at),
        "updated_at": _serialize_dt(r.updated_at),
    }


class RouteRepository(AdminRouteRepositoryPort):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def list_all(self, tenant_id: str | None = None) -> list[AdminRoute]:
        doc = await self._store.read_async()
        rows = doc["routes"]
        if tenant_id is not None:
            rows = [r for r in rows if r["tenant_id"] == tenant_id]
        return [_row_to_route(r) for r in rows]

    async def get_by_id(self, route_id: str) -> AdminRoute | None:
        doc = await self._store.read_async()
        for r in doc["routes"]:
            if r["id"] == route_id:
                return _row_to_route(r)
        return None

    async def save(self, route: AdminRoute) -> None:
        row = _route_to_row(route)

        def mut(doc: dict) -> None:
            routes = doc["routes"]
            for i, r in enumerate(routes):
                if r["id"] == route.id:
                    routes[i] = row
                    return
            routes.append(row)

        await self._store.mutate_async(mut)

    async def delete(self, route_id: str) -> bool:
        removed = False

        def mut(doc: dict) -> None:
            nonlocal removed
            before = len(doc["routes"])
            doc["routes"] = [r for r in doc["routes"] if r["id"] != route_id]
            removed = len(doc["routes"]) < before

        await self._store.mutate_async(mut)
        return removed