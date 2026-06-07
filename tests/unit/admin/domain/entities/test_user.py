import pytest
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import ValidationError
from tests.unit.conftest import now

def test_create_admin_normalizes_email_and_requires_tenant():
    u = User.create_admin(id="u1", email=" ADMIN@ACME.DEV ", password_hash="h", tenant_id="t1", now=now())
    assert u.email == "admin@acme.dev"
    assert u.role == "admin"
    assert u.tenant_id == "t1"

def test_superuser_cannot_have_tenant_and_admin_must_have_tenant():
    with pytest.raises(ValueError):
        User(id="u", email="x@y.com", password_hash="h", tenant_id="t", created_at=now(), updated_at=now(), role="superuser")
    with pytest.raises(ValueError):
        User(id="u", email="x@y.com", password_hash="h", tenant_id=None, created_at=now(), updated_at=now(), role="admin")

def test_member_permissions_are_normalized_and_reject_invalid():
    u = User.create_member(id="m", email="m@a.com", password_hash="h", tenant_id="t", permissions=["routes", "routes", "audit"], now=now())
    assert u.permissions == ["routes", "audit"]
    with pytest.raises(ValidationError):
        User.create_member(id="m2", email="m2@a.com", password_hash="h", tenant_id="t", permissions=["root"], now=now())

def test_with_permissions_only_applies_to_members():
    m = User.create_member(id="m", email="m@a.com", password_hash="h", tenant_id="t", permissions=["routes"], now=now())
    assert m.with_permissions(["audit"], now=now()).permissions == ["audit"]
    a = User.create_admin(id="a", email="a@a.com", password_hash="h", tenant_id="t", now=now())
    with pytest.raises(ValidationError):
        a.with_permissions(["audit"], now=now())
