import pytest
from src.admin.application.use_cases.register_admin_with_tenant import RegisterAdminWithTenant
from src.admin.domain.exceptions import ConflictError, ValidationError
from tests.unit.conftest import AsyncRepo, Hasher

@pytest.mark.asyncio
async def test_register_creates_tenant_then_admin_atomically_in_same_scope():
    users, tenants = AsyncRepo(), AsyncRepo()
    admin, tenant = await RegisterAdminWithTenant(users, tenants, Hasher()).execute("Admin@A.COM", "password1", " Acme ", "ACME")
    assert tenant in tenants.saved
    assert admin in users.saved
    assert admin.tenant_id == tenant.id and admin.email == "admin@a.com"

@pytest.mark.asyncio
async def test_register_rejects_duplicate_email_or_alias():
    users, tenants = AsyncRepo(), AsyncRepo()
    await RegisterAdminWithTenant(users, tenants, Hasher()).execute("a@a.com", "password1", "A", "a")
    with pytest.raises(ConflictError): await RegisterAdminWithTenant(users, tenants, Hasher()).execute("a@a.com", "password1", "B", "b")
    with pytest.raises(ConflictError): await RegisterAdminWithTenant(AsyncRepo(), tenants, Hasher()).execute("b@a.com", "password1", "A", "a")

@pytest.mark.asyncio
async def test_register_rejects_invalid_domain_values_before_saving():
    with pytest.raises(ValidationError): await RegisterAdminWithTenant(AsyncRepo(), AsyncRepo(), Hasher()).execute("bad", "short", "", "Bad Alias")
