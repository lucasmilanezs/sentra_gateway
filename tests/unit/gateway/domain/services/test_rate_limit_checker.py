import pytest
from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker
from src.gateway.domain.value_objects.http_method import HttpMethod

class Port:
    def __init__(self, allowed=True): self.allowed=allowed; self.calls=[]
    async def is_allowed(self, **kw): self.calls.append(kw); return self.allowed

def request(headers=None): return Request(method=HttpMethod.GET, path="/", headers=headers or {}, query_params={})

@pytest.mark.asyncio
async def test_no_rate_limit_skips_port():
    port=Port(); result=await RateLimitChecker(port).check(Policy(id="p", route_id="r"), request(), tenant_id="t", route_id="r")
    assert result.allowed and port.calls == []

@pytest.mark.asyncio
async def test_rate_limit_uses_forwarded_ip_and_blocks_when_port_denies():
    port=Port(False)
    result=await RateLimitChecker(port).check(Policy(id="p", route_id="r", rate_limit_per_minute=5), request({"x-forwarded-for":"1.1.1.1, 2.2.2.2"}), tenant_id="t", route_id="r")
    assert not result.allowed and result.status_code == 429
    assert port.calls[0]["client_ip"] == "1.1.1.1"
    assert port.calls[0]["limit"] == 5
