import pytest
from types import SimpleNamespace
from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.domain.exceptions import RouteNotFoundError, PolicyDeniedError, UpstreamTimeoutError
from src.gateway.interface.http.routers import gateway_router

class FastReq:
    def __init__(self, uc):
        self.method="GET"; self.url=SimpleNamespace(path="/x"); self.headers={"host":"h"}; self.query_params={}; self.path_params={}; self.client=None; self.app=SimpleNamespace(state=SimpleNamespace(gateway_request_port=uc))
    async def body(self): return b""
class UC:
    def __init__(self, result=None, exc=None): self.result=result; self.exc=exc
    async def handle(self, request, raw):
        if self.exc: raise self.exc
        return self.result

@pytest.mark.asyncio
async def test_gateway_entrypoint_returns_upstream_response(monkeypatch):
    monkeypatch.setattr(gateway_router.InstanceLoader, "gateway_request_port", lambda req: req.app.state.gateway_request_port)
    resp=await gateway_router._gateway_entrypoint(FastReq(UC(GatewayResponse(202, {"x":"y"}, b"ok"))))
    assert resp.status_code == 202 and resp.body == b"ok"

@pytest.mark.asyncio
@pytest.mark.parametrize("exc,status,code", [(RouteNotFoundError("no"),404,"ROUTE_NOT_FOUND"), (PolicyDeniedError("bad", 403),403,"POLICY_DENIED"), (UpstreamTimeoutError("timeout"),504,"UPSTREAM_TIMEOUT")])
async def test_gateway_entrypoint_maps_domain_errors(monkeypatch, exc, status, code):
    monkeypatch.setattr(gateway_router.InstanceLoader, "gateway_request_port", lambda req: req.app.state.gateway_request_port)
    resp=await gateway_router._gateway_entrypoint(FastReq(UC(exc=exc)))
    assert resp.status_code == status
    assert code.encode() in resp.body
