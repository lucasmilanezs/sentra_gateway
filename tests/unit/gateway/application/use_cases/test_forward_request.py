import pytest
from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.domain.exceptions import DomainNotFoundError, PolicyDeniedError, RouteNotFoundError, TenantNotFoundError, UpstreamError
from src.gateway.domain.models.domain import Domain
from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.models.route import Route
from src.gateway.domain.ports.tenant_repository import GatewayTenant
from src.gateway.domain.ports.upstream_proxy_port import UpstreamResponse
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.value_objects.backend_url import BackendUrl
from src.gateway.domain.value_objects.http_method import HttpMethod

class Repo:
    def __init__(self, item=None): self.item=item
    async def get_by_domain(self, host): return self.item
    async def get_by_path(self, path, method, tenant_id): return self.item
    async def get_by_id(self, id): return self.item
    async def get_by_route_id(self, id): return self.item
class Pipeline:
    def __init__(self, result): self.result=result
    async def apply(self, *a, **kw): return self.result
class Proxy:
    def __init__(self, fail=False): self.fail=fail; self.calls=[]
    async def forward(self, **kw):
        self.calls.append(kw)
        if self.fail: raise UpstreamError("boom")
        return UpstreamResponse(status_code=201, headers={"x":"y"}, body=b"ok")
class Log:
    async def write(self, event): pass

def req(): return Request(method=HttpMethod.GET, path="/api/users", headers={"host":"api.local"}, query_params={}, host="api.local")
def make_uc(tenant=None, route=None, domain=None, policy=None, result=None, proxy=None):
    return ForwardRequest(Repo(route), Repo(domain), Repo(policy), proxy or Proxy(), Log(), Pipeline(result or PolicyResult(True)), LogEventBuilder(), tenant_repository=Repo(tenant))

@pytest.mark.asyncio
async def test_forward_request_happy_path_builds_upstream_url():
    tenant=GatewayTenant(id="t", domain="api.local")
    route=Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d", methods=(HttpMethod.GET,))
    domain=Domain(id="d", name="api", backend_url=BackendUrl("http://backend"))
    proxy=Proxy(); out=await make_uc(tenant, route, domain, Policy(id="p", route_id="r"), proxy=proxy).handle(req(), b"")
    assert isinstance(out, GatewayResponse) and out.status_code == 201
    assert proxy.calls[0]["url"] == "http://backend/users"

@pytest.mark.asyncio
@pytest.mark.parametrize("tenant,route,domain,exc", [(None,None,None,TenantNotFoundError), (GatewayTenant(id="t", domain="h"),None,None,RouteNotFoundError), (GatewayTenant(id="t", domain="h"),Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d"),None,DomainNotFoundError)])
async def test_forward_request_resolution_failures(tenant, route, domain, exc):
    with pytest.raises(exc): await make_uc(tenant, route, domain).handle(req(), b"")

@pytest.mark.asyncio
async def test_policy_denial_and_upstream_error_are_propagated():
    tenant=GatewayTenant(id="t", domain="h"); route=Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d"); domain=Domain(id="d", name="api", backend_url=BackendUrl("http://b"))
    with pytest.raises(PolicyDeniedError): await make_uc(tenant, route, domain, result=PolicyResult(False, status_code=401, reason="deny")).handle(req(), b"")
    with pytest.raises(UpstreamError): await make_uc(tenant, route, domain, result=PolicyResult(True), proxy=Proxy(fail=True)).handle(req(), b"")
