import pytest
from src.admin.domain.services.access_control import TenantAccessControl
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ForbiddenError, ValidationError
from tests.unit.conftest import now

def test_superuser_bypasses_tenant_access_and_admin_is_scoped():
    TenantAccessControl.ensure_tenant_access(caller_role="superuser", caller_tenant_id=None, resource_tenant_id="t2")
    TenantAccessControl.ensure_tenant_access(caller_role="admin", caller_tenant_id="t1", resource_tenant_id="t1")
    with pytest.raises(ForbiddenError):
        TenantAccessControl.ensure_tenant_access(caller_role="admin", caller_tenant_id="t1", resource_tenant_id="t2")

def test_member_target_tenant_resolution():
    with pytest.raises(ForbiddenError): TenantAccessControl.resolve_member_target_tenant(caller_role="admin", caller_tenant_id="t1", target_tenant_id="t2")
    assert TenantAccessControl.resolve_member_target_tenant(caller_role="admin", caller_tenant_id="t1", target_tenant_id=None) == "t1"
    assert TenantAccessControl.resolve_member_target_tenant(caller_role="superuser", caller_tenant_id=None, target_tenant_id="t2") == "t2"
    with pytest.raises(ValidationError): TenantAccessControl.resolve_member_target_tenant(caller_role="superuser", caller_tenant_id=None, target_tenant_id=None)
    with pytest.raises(ForbiddenError): TenantAccessControl.resolve_member_target_tenant(caller_role="member", caller_tenant_id="t1", target_tenant_id="t1")

def test_modify_member_requires_member_target_and_authorized_tenant():
    m = User.create_member(id="m", email="m@x.com", password_hash="h", tenant_id="t1", permissions=["routes"], now=now())
    TenantAccessControl.ensure_can_modify_member(caller_role="admin", caller_tenant_id="t1", target=m)
    with pytest.raises(ForbiddenError): TenantAccessControl.ensure_can_modify_member(caller_role="admin", caller_tenant_id="t2", target=m)
    a = User.create_admin(id="a", email="a@x.com", password_hash="h", tenant_id="t1", now=now())
    with pytest.raises(ForbiddenError): TenantAccessControl.ensure_can_modify_member(caller_role="admin", caller_tenant_id="t1", target=a)
