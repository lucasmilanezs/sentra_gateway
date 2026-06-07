from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_components import ForbiddenHeadersPolicy, ForbiddenParamsPolicy, RequiredHeadersPolicy, RequiredParamsPolicy
from src.gateway.domain.value_objects.http_method import HttpMethod

def req(): return Request(method=HttpMethod.GET, path="/", headers={"Authorization":"x", "x-bad":"1"}, query_params={"page":"1", "debug":"true"})

def test_required_and_forbidden_headers_are_case_insensitive():
    assert RequiredHeadersPolicy().evaluate(Policy(id="p", route_id="r", required_headers=("authorization",)), req()).passed
    assert not RequiredHeadersPolicy().evaluate(Policy(id="p", route_id="r", required_headers=("x-missing",)), req()).passed
    assert not ForbiddenHeadersPolicy().evaluate(Policy(id="p", route_id="r", forbidden_headers=("X-BAD",)), req()).passed

def test_required_and_forbidden_params():
    assert RequiredParamsPolicy().evaluate(Policy(id="p", route_id="r", required_params=("page",)), req()).passed
    assert not RequiredParamsPolicy().evaluate(Policy(id="p", route_id="r", required_params=("tenant",)), req()).passed
    assert not ForbiddenParamsPolicy().evaluate(Policy(id="p", route_id="r", forbidden_params=("debug",)), req()).passed
