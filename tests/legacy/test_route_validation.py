import pytest

from src.admin.domain.exceptions import ValidationError
from src.admin.domain.services.route_validation import validate_path_pattern


def test_valid_path():
    assert validate_path_pattern("/v1/users") == "/v1/users"


def test_rejects_uppercase():
    with pytest.raises(ValidationError):
        validate_path_pattern("/v1/Users")


def test_rejects_double_slash():
    with pytest.raises(ValidationError):
        validate_path_pattern("/v1//users")
