import sys
import types

fake_deps = types.ModuleType("src.admin.interface.http.dependencies")
fake_deps.get_current_claims = lambda: None
fake_deps.get_manage_sub_user = lambda: None
fake_deps.require_admin = lambda: (lambda: None)
fake_deps.require_permission = lambda permission: (lambda: None)
fake_deps.require_superuser = lambda: (lambda: None)
sys.modules["src.admin.interface.http.dependencies"] = fake_deps

import pytest
from src.admin.interface.http.routers.sub_user_router import _create_sub_user_for_tenant, _to_response
from src.admin.interface.schema.sub_user_schema import SubUserCreate
from src.admin.domain.entities.user import User
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from tests.unit.conftest import now


class UC:
    def __init__(self):
        self.kw = None

    async def create(self, **kw):
        self.kw = kw
        return User.create_member(
            id="m",
            email=kw["email"],
            password_hash="h",
            tenant_id=kw["target_tenant_id"] or kw["caller_tenant_id"],
            permissions=kw["permissions"],
            now=now(),
        )


@pytest.mark.asyncio
async def test_create_sub_user_for_tenant_passes_claim_scope_and_returns_response():
    uc = UC()
    body = SubUserCreate(email="m@a.com", password="password1", permissions=["routes"], tenant_id=None)
    claims = JwtClaims(sub="admin", email="a@a.com", tenant_id="t1", role="admin")
    resp = await _create_sub_user_for_tenant(body=body, tenant_id="t1", claims=claims, uc=uc)
    assert resp.email == "m@a.com"
    assert uc.kw["caller_role"] == "admin" and uc.kw["caller_user_id"] == "admin"


def test_to_response_does_not_leak_password_hash():
    resp = _to_response(
        User.create_member(id="m", email="m@a.com", password_hash="secret", tenant_id="t", permissions=["routes"], now=now())
    )
    assert not hasattr(resp, "password_hash")
