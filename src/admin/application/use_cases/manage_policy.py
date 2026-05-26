import uuid
from datetime import datetime, timezone
from src.admin.application.services.tenant_ownership_guard import TenantOwnershipGuard
from src.admin.domain.entities.policy import Policy
from src.admin.domain.exceptions import NotFoundError, ValidationError
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.infrastructure.pubsub.redis_publisher import RedisPublisher

def _utcnow():
    return datetime.now(timezone.utc)

class ManagePolicy:
    def __init__(self, policies, routes, publisher=None):
        self._policies = policies
        self._routes = routes
        self._publisher = publisher

    async def get_by_route(self, *, caller_role, caller_tenant_id, route_id):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        return await self._policies.get_by_route_id(route_id)

    async def upsert(self, *, caller_role, caller_tenant_id, route_id, requires_auth, rate_limit_per_minute, allowed_roles,
                     jwt_validate_exp=True, jwt_issuer=None, jwt_audience=None, jwt_clock_skew_seconds=30,
                     required_headers=None, forbidden_headers=None, required_params=None, forbidden_params=None):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        if rate_limit_per_minute is not None and rate_limit_per_minute <= 0:
            raise ValidationError("rate_limit_per_minute deve ser maior que zero")
        existing = await self._policies.get_by_route_id(route_id)
        now = _utcnow()
        policy = Policy(
            id=existing.id if existing else str(uuid.uuid4()), route_id=route_id,
            requires_auth=requires_auth, rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles, jwt_validate_exp=jwt_validate_exp,
            jwt_issuer=jwt_issuer, jwt_audience=jwt_audience, jwt_clock_skew_seconds=jwt_clock_skew_seconds,
            required_headers=required_headers or [], forbidden_headers=forbidden_headers or [],
            required_params=required_params or [], forbidden_params=forbidden_params or [],
            created_at=existing.created_at if existing else now, updated_at=now,
        )
        await self._policies.save(policy)
        if self._publisher:
            await self._publisher.notify_config_updated()
        return policy

    async def delete(self, *, caller_role, caller_tenant_id, route_id):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantOwnershipGuard.assert_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        deleted = await self._policies.delete_by_route_id(route_id)
        if not deleted:
            raise NotFoundError("política não encontrada para esta rota")
        if self._publisher:
            await self._publisher.notify_config_updated()
