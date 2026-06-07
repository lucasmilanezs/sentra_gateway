import pytest
from src.admin.domain.entities.tenant import Tenant
from src.admin.domain.exceptions import ValidationError
from tests.unit.conftest import now

def test_tenant_normalization_and_suggestions():
    t = Tenant.create(id="t1", name=" Acme ", alias="ACME-01", now=now())
    assert t.name == "Acme"
    assert t.alias == "acme-01"
    assert "api.acme-01.local" in t.domain_suggestions()

def test_rejects_invalid_tenant_name_and_alias():
    with pytest.raises(ValidationError): Tenant.normalize_name("")
    with pytest.raises(ValidationError): Tenant.normalize_alias("Bad Alias")
    with pytest.raises(ValidationError): Tenant.normalize_alias("-bad")

def test_with_updates_preserves_id_and_created_at():
    t = Tenant.create(id="t1", name="A", alias="a", now=now())
    updated = t.with_updates(name="B", alias="b", now=now())
    assert updated.id == t.id and updated.created_at == t.created_at
    assert updated.name == "B" and updated.alias == "b"
