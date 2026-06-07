import pytest
from src.admin.domain.exceptions import ValidationError
from src.admin.domain.services.route_validation import validate_backend_url, validate_path_pattern

def test_validate_path_pattern_normalizes_and_rejects_bad_shapes():
    assert validate_path_pattern(" /v1/users ") == "/v1/users"
    for bad in ["", "v1/users", "/v1//users", "/v1/Users", "/v1/users?x=1"]:
        with pytest.raises(ValidationError): validate_path_pattern(bad)

def test_validate_backend_url_accepts_http_and_https_only():
    assert validate_backend_url(" https://api.example.com/base ") == "https://api.example.com/base"
    for bad in ["", "ftp://x", "http://", "api.example.com"]:
        with pytest.raises(ValidationError): validate_backend_url(bad)
