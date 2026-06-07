import sys
import types

fake_deps = types.ModuleType("src.admin.interface.http.dependencies")
fake_deps.get_current_claims = lambda: None
fake_deps.get_manage_route = lambda: None
fake_deps.get_manage_sub_user = lambda: None
fake_deps.require_permission = lambda permission: (lambda: None)
fake_deps.require_admin = lambda: (lambda: None)
fake_deps.require_superuser = lambda: (lambda: None)
sys.modules["src.admin.interface.http.dependencies"] = fake_deps

from src.admin.interface.http.routers.admin_route_router import _to_response
from src.admin.domain.entities.admin_route import AdminRoute
from src.admin.domain.value_objects.http_method import HttpMethod
from tests.unit.conftest import now


def test_route_response_maps_domain_route_without_mutating_methods():
    route = AdminRoute(
        id="r",
        tenant_id="t",
        path_pattern="/x",
        methods=[HttpMethod.GET],
        backend_url="http://b",
        display_color="#2dd4bf",
        created_at=now(),
        updated_at=now(),
    )
    resp = _to_response(route)
    assert resp.id == "r" and resp.tenant_id == "t"
    assert resp.methods == [HttpMethod.GET]
