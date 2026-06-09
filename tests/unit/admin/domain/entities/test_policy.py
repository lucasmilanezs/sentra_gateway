import pytest
from src.admin.domain.entities.policy import Policy
from src.admin.domain.exceptions import ValidationError

def test_auth_mode_is_derived_from_legacy_requires_auth_flags():
    assert Policy(id="p", route_id="r").auth_mode == Policy.AUTH_NONE
    assert Policy(id="p", route_id="r", requires_auth=True).auth_mode == Policy.AUTH_JWT_CLAIMS
    assert Policy(id="p", route_id="r", requires_auth=True, jwt_validate_exp=False).auth_mode == Policy.AUTH_JWT_STRUCTURAL

def test_auth_mode_and_signing_algorithm_are_normalized():
    p = Policy(id="p", route_id="r", auth_mode=" JWT_SIGNED ", jwt_signing_algorithm=" hs256 ", jwt_signing_key_configured=True)
    assert p.auth_mode == "jwt_signed"
    assert p.jwt_signing_algorithm == "HS256"

def test_invalid_auth_mode_algorithm_and_clock_skew_are_rejected():
    with pytest.raises(ValidationError): Policy(id="p", route_id="r", auth_mode="invalid")
    with pytest.raises(ValidationError): Policy(id="p", route_id="r", jwt_signing_algorithm="none")
    with pytest.raises(ValidationError): Policy(id="p", route_id="r", jwt_clock_skew_seconds=999)
