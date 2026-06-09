import pytest
from src.admin.domain.value_objects.permission import Permission
from src.admin.domain.exceptions import ValidationError

def test_permission_values_are_deduplicated_preserving_order():
    assert Permission.normalize_many(["routes", "routes", "audit"]) == ["routes", "audit"]

def test_permission_validation_rejects_invalid_and_empty_when_required():
    with pytest.raises(ValidationError): Permission.normalize_many(["root"])
    with pytest.raises(ValidationError): Permission.normalize_many([], require_non_empty=True)
