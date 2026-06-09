import pytest
from src.admin.application.use_cases.manage_sub_user import ManageSubUser
from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.unit.conftest import AsyncRepo, Hasher, now

@pytest.mark.asyncio
async def test_admin_creates_member_in_own_tenant_ignoring_other_target():
    tenants = AsyncRepo(t1=Tenant.create(id="t1", name="Acme", alias="acme", now=now()))
    users = AsyncRepo()
    audit = AsyncRepo()
    user = await ManageSubUser(users, tenants, Hasher(), audit).create(caller_role="admin", caller_tenant_id="t1", email="m@a.com", password="password1", permissions=["routes"], target_tenant_id="t1", caller_user_id="admin")
    assert user.role == "member" and user.tenant_id == "t1"
    assert audit.recorded[-1].action == "CREATE"

@pytest.mark.asyncio
async def test_create_member_rejects_invalid_actor_tenant_password_permission_and_duplicate():
    tenants=AsyncRepo(t1=Tenant.create(id="t1", name="Acme", alias="acme", now=now()))
    users=AsyncRepo(existing=User.create_member(id="e", email="m@a.com", password_hash="h", tenant_id="t1", permissions=["routes"], now=now()))
    uc=ManageSubUser(users, tenants, Hasher())
    with pytest.raises(ForbiddenError): await uc.create(caller_role="member", caller_tenant_id="t1", email="x@a.com", password="password1", permissions=["routes"])
    with pytest.raises(NotFoundError): await uc.create(caller_role="superuser", caller_tenant_id=None, target_tenant_id="missing", email="x@a.com", password="password1", permissions=["routes"])
    with pytest.raises(ValidationError): await uc.create(caller_role="admin", caller_tenant_id="t1", email="x@a.com", password="short", permissions=["routes"])
    with pytest.raises(ValidationError): await uc.create(caller_role="admin", caller_tenant_id="t1", email="x@a.com", password="password1", permissions=[])
    with pytest.raises(ConflictError): await uc.create(caller_role="admin", caller_tenant_id="t1", email="m@a.com", password="password1", permissions=["routes"])

@pytest.mark.asyncio
async def test_list_update_and_delete_member_are_tenant_scoped():
    member = User.create_member(id="m", email="m@a.com", password_hash="h", tenant_id="t1", permissions=["routes"], now=now())
    users = AsyncRepo(m=member); tenants = AsyncRepo(t=object()); audit=AsyncRepo()
    uc=ManageSubUser(users, tenants, Hasher(), audit)
    assert await uc.list_by_tenant(caller_role="admin", caller_tenant_id="t1", tenant_id="t1") == [member]
    with pytest.raises(ForbiddenError): await uc.list_by_tenant(caller_role="admin", caller_tenant_id="t2", tenant_id="t1")
    updated = await uc.update_permissions(caller_role="admin", caller_tenant_id="t1", user_id="m", permissions=["audit"], caller_user_id="a")
    assert updated.permissions == ["audit"]
    await uc.delete(caller_role="admin", caller_tenant_id="t1", user_id="m", caller_user_id="a")
    assert users.deleted == ["m"]
    assert audit.recorded[-1].action == "DELETE"
