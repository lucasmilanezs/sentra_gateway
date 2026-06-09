import pytest
from src.gateway.application.use_cases.apply_policy_pipeline import ApplyPolicyPipeline
from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyEvaluationDetail, PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.value_objects.http_method import HttpMethod

class Eval:
    def __init__(self, result): self.result=result
    def evaluate(self, policy, request): return self.result
class Rate:
    def __init__(self, result): self.result=result
    async def check(self, policy, request, **kw): return self.result
req=Request(method=HttpMethod.GET, path="/", headers={}, query_params={})

@pytest.mark.asyncio
async def test_none_policy_allows_without_evaluator():
    out=await ApplyPolicyPipeline(Eval(PolicyResult(False))).apply(None, req, tenant_id="t", route_id="r")
    assert out.allowed

@pytest.mark.asyncio
async def test_evaluator_denial_short_circuits_rate_limit():
    rate=Rate(PolicyResult(True))
    out=await ApplyPolicyPipeline(Eval(PolicyResult(False, status_code=401, reason="bad")), rate).apply(Policy(id="p", route_id="r"), req, tenant_id="t", route_id="r")
    assert not out.allowed and out.reason == "bad"

@pytest.mark.asyncio
async def test_rate_limit_denial_merges_checks():
    base=PolicyResult(True, checks=(PolicyEvaluationDetail("auth", True, "ok"),))
    rl=PolicyResult(False, status_code=429, reason="limit", checks=(PolicyEvaluationDetail("rate", False, "no"),))
    out=await ApplyPolicyPipeline(Eval(base), Rate(rl)).apply(Policy(id="p", route_id="r"), req, tenant_id="t", route_id="r")
    assert not out.allowed and out.status_code == 429 and [c.check for c in out.checks] == ["auth", "rate"]
