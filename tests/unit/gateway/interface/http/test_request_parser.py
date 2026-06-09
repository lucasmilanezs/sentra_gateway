from types import SimpleNamespace
from src.gateway.interface.http.request_parser import RequestParser
from src.gateway.domain.value_objects.http_method import HttpMethod

class Headers(dict):
    def get(self, key, default=None):
        for k,v in self.items():
            if k.lower()==key.lower(): return v
        return default

def test_request_parser_filters_hop_by_hop_headers_and_injects_client_ip():
    fastapi_request=SimpleNamespace(method="get", url=SimpleNamespace(path="/v1"), headers=Headers({"Host":"api.local", "Connection":"close", "X-Test":"1"}), query_params={"a":"b"}, path_params={"id":"1"}, client=SimpleNamespace(host="10.0.0.1"))
    parsed=RequestParser().parse(fastapi_request)
    assert parsed.method == HttpMethod.GET
    assert "Connection" not in parsed.headers
    assert parsed.headers["x-forwarded-for"] == "10.0.0.1"
    assert parsed.host == "api.local"
    assert parsed.params[0].name == "id"
