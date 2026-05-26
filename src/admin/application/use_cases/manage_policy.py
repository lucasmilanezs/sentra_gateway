import uuid
from datetime import datetime, timezone
from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.entities.policy import Policy
from src.admin.domain.exceptions import NotFoundError, ValidationError
from src.admin.domain.services.policy_validation import ensure_valid_rate_limit
from src.admin.domain.ports.admin_route_repository import AdminRouteRepositoryPort
from src.admin.domain.ports.policy_repository import PolicyRepositoryPort
from src.admin.domain.ports.config_notifier import ConfigNotifier
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory

def _utcnow():
    return datetime.now(timezone.utc)

class ManagePolicy:
    def __init__(self, policies, routes, publisher=None, change_audit: ChangeAuditRepositoryPort | None = None):
        self._policies = policies
        self._routes = routes
        self._publisher = publisher
        self._change_audit = change_audit

    async def get_by_route(self, *, caller_role, caller_tenant_id, route_id):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        return await self._policies.get_by_route_id(route_id)

    async def upsert(self, *, caller_role, caller_tenant_id, route_id, requires_auth, rate_limit_per_minute, allowed_roles,
                     jwt_validate_exp=True, jwt_issuer=None, jwt_audience=None, jwt_clock_skew_seconds=30,
                     required_headers=None, forbidden_headers=None, required_params=None, forbidden_params=None,
                     caller_user_id=None):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        ensure_valid_rate_limit(rate_limit_per_minute)
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
        await self._record_change(
            tenant_id=route.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role,
            action="UPDATE" if existing else "CREATE", resource_type="policy", resource_id=policy.id,
            resource_summary=f"route policy for {route.path_pattern}",
            detail={"route_id": route_id, "requires_auth": requires_auth, "rate_limit_per_minute": rate_limit_per_minute, "allowed_roles": allowed_roles, "required_headers": required_headers or [], "forbidden_headers": forbidden_headers or [], "required_params": required_params or [], "forbidden_params": forbidden_params or []},
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
        return policy

    async def delete(self, *, caller_role, caller_tenant_id, route_id, caller_user_id=None):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(caller_role=caller_role, caller_tenant_id=caller_tenant_id, resource_tenant_id=route.tenant_id)
        deleted = await self._policies.delete_by_route_id(route_id)
        if not deleted:
            raise NotFoundError("política não encontrada para esta rota")
        await self._record_change(
            tenant_id=route.tenant_id, actor_id=caller_user_id or "unknown", actor_role=caller_role,
            action="DELETE", resource_type="policy", resource_id=route_id,
            resource_summary=f"route policy for {route.path_pattern}", detail={"route_id": route_id},
        )
        if self._publisher:
            await self._publisher.notify_config_updated()

    async def _record_change(self, *, tenant_id, actor_id, actor_role, action, resource_type, resource_id, resource_summary, detail=None):
        if not self._change_audit:
            return
        await self._change_audit.record(GovernanceAuditEventFactory.build(
            tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role or "unknown",
            action=action, resource_type=resource_type, resource_id=resource_id,
            resource_summary=resource_summary, detail=detail,
        ))
