from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.value_objects.http_method import HttpMethod

def req(auth=None):
    headers={} if auth is None else {"authorization": auth}
    return Request(method=HttpMethod.GET, path="/", headers=headers, query_params={})

def test_none_and_bearer_modes():
    ev=PolicyEvaluator()
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="none"), req()).allowed
    assert not ev.evaluate(Policy(id="p", route_id="r", auth_mode="bearer"), req()).allowed
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="bearer"), req("Bearer abc")).allowed

def test_structural_claims_and_signed_jwt_paths_use_mocked_jose():
    ev=PolicyEvaluator()
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="jwt_structural"), req("Bearer a.b.c")).allowed
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="jwt_claims", jwt_issuer="issuer", jwt_audience="audience"), req("Bearer a.b.c")).allowed
    assert not ev.evaluate(Policy(id="p", route_id="r", auth_mode="jwt_claims", jwt_issuer="other"), req("Bearer a.b.c")).allowed
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="jwt_signed", jwt_signing_key="secret", jwt_signing_algorithm="HS256"), req("Bearer a.b.c")).allowed
    assert ev.evaluate(Policy(id="p", route_id="r", auth_mode="jwt_signed"), req("Bearer a.b.c")).status_code == 503
