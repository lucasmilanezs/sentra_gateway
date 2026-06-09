import pytest
from src.admin.domain.exceptions import AuthError, ConflictError, NotFoundError, ValidationError
from src.admin.interface.http.exception_handlers import auth_error_handler, conflict_handler, not_found_handler, validation_error_handler

@pytest.mark.asyncio
async def test_exception_handlers_map_domain_errors_to_http_statuses():
    assert (await not_found_handler(None, NotFoundError("missing"))).status_code == 404
    assert (await conflict_handler(None, ConflictError("conflict"))).status_code == 409
    assert (await validation_error_handler(None, ValidationError("bad"))).status_code == 422
    resp = await auth_error_handler(None, AuthError("no"))
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
