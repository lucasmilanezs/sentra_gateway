import uuid
from datetime import datetime, timezone

from src.admin.application.services.tenant_ownership_guard import TenantOwnershipGuard
from src.admin.domain.entities.policy import Policy
from src.admin.domain.exceptions import AuthError, NotFoundError, ValidationError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.infrastructure.pubsub.redis_publisher import RedisPublisher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManagePolicy:
    """
    Use case for managing security policies linked to gateway routes.

    Each route has at most one policy. Creating a policy for a route
    that already has one replaces it (upsert semantics).
    Publishes a config update notification after every write so the
    gateway reloads its snapshot without requiring a restart.
    """

    def __init__(
        self,
        policies: PolicyRepositoryPort,
        routes: AdminRouteRepositoryPort,
        publisher: RedisPublisher | None = None,
    ) -> None:
        self._policies = policies
        self._routes = routes
        self._publisher = publisher

    async def get_by_route(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
    ) -> Policy | None:
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        return await self._policies.get_by_route_id(route_id)

    async def upsert(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
        requires_auth: bool,
        rate_limit_per_minute: int | None,
        allowed_roles: list[str],
        jwt_validate_exp: bool = True,
        jwt_issuer: str | None = None,
        jwt_audience: str | None = None,
        jwt_clock_skew_seconds: int = 30,
    ) -> Policy:
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )

        if rate_limit_per_minute is not None and rate_limit_per_minute <= 0:
            raise ValidationError("rate_limit_per_minute deve ser maior que zero")

        existing = await self._policies.get_by_route_id(route_id)
        now = _utcnow()

        policy = Policy(
            id=existing.id if existing else str(uuid.uuid4()),
            route_id=route_id,
            requires_auth=requires_auth,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles,
            jwt_validate_exp=jwt_validate_exp,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            jwt_clock_skew_seconds=jwt_clock_skew_seconds,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )

        await self._policies.save(policy)

        if self._publisher:
            await self._publisher.notify_config_updated()

        return policy

    async def delete(
        self,
        *,
        caller_role: str,
        caller_tenant_id: str | None,
        route_id: str,
    ) -> None:
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        deleted = await self._policies.delete_by_route_id(route_id)
        if not deleted:
            raise NotFoundError("política não encontrada para esta rota")

        if self._publisher:
            await self._publisher.notify_config_updated()
