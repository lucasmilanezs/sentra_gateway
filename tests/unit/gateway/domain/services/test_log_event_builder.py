from src.gateway.domain.models.policy_result import PolicyEvaluationDetail, PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.value_objects.http_method import HttpMethod

def test_log_event_contains_sanitized_preview_policy_checks_and_layer_errors():
    req=Request(method=HttpMethod.POST, path="/x", headers={"x-real-ip":"9.9.9.9"}, query_params={"a":"b"})
    result=PolicyResult(allowed=True, checks=(PolicyEvaluationDetail("required_headers", True, "ok"),))
    ev=LogEventBuilder().build(req, "http://up", 200, 1.5, route_id="r", tenant_id="t", policy_result=result, upstream_response_body=b"hello"*200, layer_errors={"domain":"none"})
    assert ev.client_ip == "9.9.9.9"
    assert ev.policy_checks[0]["check"] == "required_headers"
    assert len(ev.upstream_response_body_preview) <= 512
    assert ev.layer_errors == {"domain":"none"}
