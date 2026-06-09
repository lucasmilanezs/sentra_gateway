import uuid
from datetime import datetime, timezone

from src.admin.application.services.governance_audit_recorder import GovernanceAuditRecorder
from src.admin.domain.entities.policy import Policy
from src.admin.domain.exceptions import NotFoundError
from src.admin.domain.ports.change_audit_repository import ChangeAuditRepositoryPort
from src.admin.domain.services.access_control import TenantAccessControl


def _utcnow():
    return datetime.now(timezone.utc)


class ManagePolicy:
    def __init__(self, policies, routes, publisher=None, change_audit: ChangeAuditRepositoryPort | None = None):
        self._policies = policies
        self._routes = routes
        self._publisher = publisher
        self._audit = GovernanceAuditRecorder(change_audit)

    async def get_by_route(self, *, caller_role, caller_tenant_id, route_id):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        return await self._policies.get_by_route_id(route_id)

    async def upsert(
        self,
        *,
        caller_role,
        caller_tenant_id,
        route_id,
        auth_mode="none",
        requires_auth=None,
        rate_limit_per_minute=None,
        allowed_roles=None,
        jwt_validate_exp=True,
        jwt_issuer=None,
        jwt_audience=None,
        jwt_clock_skew_seconds=30,
        jwt_signing_algorithm=None,
        jwt_signing_key=None,
        required_headers=None,
        forbidden_headers=None,
        required_params=None,
        forbidden_params=None,
        caller_user_id=None,
    ):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )

        existing = await self._policies.get_by_route_id(route_id)
        now = _utcnow()
        data = dict(
            requires_auth=bool(requires_auth) if requires_auth is not None else auth_mode != Policy.AUTH_NONE,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_roles=allowed_roles or [],
            auth_mode=auth_mode,
            jwt_validate_exp=jwt_validate_exp,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            jwt_clock_skew_seconds=jwt_clock_skew_seconds,
            jwt_signing_algorithm=jwt_signing_algorithm,
            jwt_signing_key=jwt_signing_key,
            required_headers=required_headers or [],
            forbidden_headers=forbidden_headers or [],
            required_params=required_params or [],
            forbidden_params=forbidden_params or [],
        )
        policy = (
            existing.reconfigure(now=now, **data)
            if existing
            else Policy.create_for_route(id=str(uuid.uuid4()), route_id=route_id, now=now, **data)
        )
        await self._policies.save(policy)
        await self._audit.record(
            tenant_id=route.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="UPDATE" if existing else "CREATE",
            resource_type=policy.audit_resource_type(),
            resource_id=policy.id,
            resource_summary=f"route policy for {route.path_pattern}",
            detail=policy.audit_detail(),
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
        return policy

    async def delete(self, *, caller_role, caller_tenant_id, route_id, caller_user_id=None):
        route = await self._routes.get_by_id(route_id)
        if not route:
            raise NotFoundError("rota não encontrada")
        TenantAccessControl.ensure_tenant_access(
            caller_role=caller_role,
            caller_tenant_id=caller_tenant_id,
            resource_tenant_id=route.tenant_id,
        )
        deleted = await self._policies.delete_by_route_id(route_id)
        if not deleted:
            raise NotFoundError("política não encontrada para esta rota")
        await self._audit.record(
            tenant_id=route.tenant_id,
            actor_id=caller_user_id,
            actor_role=caller_role,
            action="DELETE",
            resource_type="policy",
            resource_id=route_id,
            resource_summary=f"route policy for {route.path_pattern}",
            detail={"route_id": route_id},
        )
        if self._publisher:
            await self._publisher.notify_config_updated()
