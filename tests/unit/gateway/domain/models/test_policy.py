from src.gateway.domain.models.policy import Policy

def test_policy_auth_mode_derivation_and_safe_invalid_fallbacks():
    assert Policy(id="p", route_id="r").auth_mode == "none"
    assert Policy(id="p", route_id="r", requires_auth=True).auth_mode == "jwt_claims"
    assert Policy(id="p", route_id="r", requires_auth=True, jwt_validate_exp=False).auth_mode == "jwt_structural"
    assert Policy(id="p", route_id="r", auth_mode="unknown").auth_mode == "none"

def test_negative_clock_skew_is_clamped_to_zero():
    assert Policy(id="p", route_id="r", jwt_clock_skew_seconds=-10).jwt_clock_skew_seconds == 0
