from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import Response

from src.gateway.application.use_cases.forward_request import (
    DomainNotFoundError,
    PolicyDeniedError,
    RouteNotFoundError,
    TenantNotFoundError,
)
from src.gateway.interface.http.instance_loader import InstanceLoader
from src.gateway.interface.http.request_parser import RequestParser
from src.gateway.interface.schema.error_response import ErrorResponse

router = APIRouter()

_parser = RequestParser()

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
_PATH = "/{path:path}"


def _error_response(status_code: int, code: str, message: str) -> Response:
    return Response(
        content=ErrorResponse(code=code, message=message).model_dump_json(),
        status_code=status_code,
        media_type="application/json",
    )


async def _gateway_entrypoint(fastapi_request: FastAPIRequest) -> Response:
    """
    HttpRouter — single entry point for all proxied requests.

    Responsibilities (interface layer only):
      1. Read the raw body once (streaming body can only be read once).
      2. Parse the FastAPI request into a domain Request via RequestParser.
      3. Load the use-case instance from app state via InstanceLoader.
      4. Invoke the inbound port and translate the result to an HTTP Response.
      5. Map domain exceptions to standard HTTP error responses.

    No business logic lives here.
    """
    raw_body = await fastapi_request.body()
    domain_request = _parser.parse(fastapi_request)
    use_case = InstanceLoader.gateway_request_port(fastapi_request)

    try:
        gateway_response = await use_case.handle(domain_request, raw_body)
    except TenantNotFoundError as exc:
        return _error_response(404, "TENANT_NOT_FOUND", str(exc))
    except RouteNotFoundError as exc:
        return _error_response(404, "ROUTE_NOT_FOUND", str(exc))
    except DomainNotFoundError as exc:
        return _error_response(502, "DOMAIN_NOT_CONFIGURED", str(exc))
    except PolicyDeniedError as exc:
        return _error_response(exc.status_code, "POLICY_DENIED", exc.reason)
    except Exception:
        return _error_response(502, "UPSTREAM_ERROR", "Failed to reach the upstream backend.")

    return Response(
        content=gateway_response.body,
        status_code=gateway_response.status_code,
        headers=gateway_response.headers,
    )


for _method in _METHODS:
    router.add_api_route(
        _PATH,
        _gateway_entrypoint,
        methods=[_method],
    )
