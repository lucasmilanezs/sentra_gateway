from src.gateway.domain.models.policy_result import PolicyEvaluationDetail, PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.audit_event_builder import AuditEventBuilder
from src.gateway.domain.value_objects.http_method import HttpMethod

def req(): return Request(method=HttpMethod.GET, path="/x", headers={"x-forwarded-for":"1.1.1.1, 2.2.2.2"}, query_params={})

def test_build_success_and_policy_denial_events():
    b=AuditEventBuilder()
    ok=b.build_success(request=req(), tenant_id="t", route_id="r", upstream_url="http://u", upstream_status_code=200, latency_ms=12)
    assert ok.outcome == "SUCCESS" and ok.client_ip == "1.1.1.1"
    denied=b.build_policy_denial(request=req(), tenant_id="t", route_id="r", policy_result=PolicyResult(allowed=False, status_code=401, reason="bad", checks=(PolicyEvaluationDetail("jwt", False, "bad"),)))
    assert denied.outcome == "POLICY_DENIED" and denied.denial_check == "jwt"
