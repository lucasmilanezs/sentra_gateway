import uuid
from datetime import datetime, timezone

from src.admin.domain.entities.policy import Policy
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.infrastructure.persistence.json.store import DocumentStore, _parse_dt, _serialize_dt


def _row_to_policy(row: dict) -> Policy:
    return Policy(
        id=row["id"],
        route_id=row["route_id"],
        requires_auth=row.get("requires_auth", False),
        rate_limit_per_minute=row.get("rate_limit_per_minute"),
        allowed_roles=row.get("allowed_roles", []),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _policy_to_row(p: Policy) -> dict:
    return {
        "id": p.id,
        "route_id": p.route_id,
        "requires_auth": p.requires_auth,
        "rate_limit_per_minute": p.rate_limit_per_minute,
        "allowed_roles": p.allowed_roles,
        "created_at": _serialize_dt(p.created_at),
        "updated_at": _serialize_dt(p.updated_at),
    }


class PolicyRepository(PolicyRepositoryPort):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def get_by_route_id(self, route_id: str) -> Policy | None:
        doc = await self._store.read_async()
        for row in doc.get("policies", []):
            if row["route_id"] == route_id:
                return _row_to_policy(row)
        return None

    async def get_by_id(self, policy_id: str) -> Policy | None:
        doc = await self._store.read_async()
        for row in doc.get("policies", []):
            if row["id"] == policy_id:
                return _row_to_policy(row)
        return None

    async def save(self, policy: Policy) -> None:
        row = _policy_to_row(policy)

        def mut(doc: dict) -> None:
            if "policies" not in doc:
                doc["policies"] = []
            policies = doc["policies"]
            for i, p in enumerate(policies):
                if p["id"] == policy.id:
                    policies[i] = row
                    return
            policies.append(row)

        await self._store.mutate_async(mut)

    async def delete_by_route_id(self, route_id: str) -> bool:
        removed = False

        def mut(doc: dict) -> None:
            nonlocal removed
            policies = doc.get("policies", [])
            before = len(policies)
            doc["policies"] = [p for p in policies if p["route_id"] != route_id]
            removed = len(doc["policies"]) < before

        await self._store.mutate_async(mut)
        return removed