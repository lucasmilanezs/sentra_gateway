import pytest
from src.gateway.domain.models.route import Route
from src.gateway.domain.value_objects.http_method import HttpMethod

def test_route_matches_exact_prefix_wildcard_and_methods():
    r=Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d", methods=(HttpMethod.GET,))
    assert r.matches("/api", "GET")
    assert r.matches("/api/users", "GET")
    assert not r.matches("/apix", "GET")
    assert not r.matches("/api", "POST")
    assert Route(id="root", tenant_id="t", path_prefix="/", domain_id="d").matches("/anything", "DELETE")

def test_strip_prefix_preserves_slash_for_backend_path():
    r=Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d")
    assert r.strip_prefix("/api") == "/"
    assert r.strip_prefix("/api/users") == "/users"
    assert r.strip_prefix("/other") == "/other"

def test_invalid_method_raises_value_error():
    r=Route(id="r", tenant_id="t", path_prefix="/api", domain_id="d", methods=(HttpMethod.GET,))
    with pytest.raises(ValueError): r.matches("/api", "INVALID")
