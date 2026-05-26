from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import Response
from src.gateway.domain.exceptions import (
    DomainNotFoundError, PolicyDeniedError, RouteNotFoundError, TenantNotFoundError,
    UpstreamConnectionRefusedError, UpstreamDNSError, UpstreamError,
    UpstreamTimeoutError, UpstreamUnreachableError,
)
from src.gateway.interface.http.instance_loader import InstanceLoader
from src.gateway.interface.http.request_parser import RequestParser
from src.gateway.interface.schema.error_response import ErrorResponse

router = APIRouter()
_parser = RequestParser()
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
_PATH = "/{path:path}"

def _error_response(status_code: int, code: str, message: str) -> Response:
    return Response(content=ErrorResponse(code=code, message=message).model_dump_json(), status_code=status_code, media_type="application/json")

async def _gateway_entrypoint(fastapi_request: FastAPIRequest) -> Response:
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
    except UpstreamTimeoutError:
        return _error_response(504, "UPSTREAM_TIMEOUT", "O backend não respondeu a tempo.")
    except UpstreamConnectionRefusedError:
        return _error_response(502, "UPSTREAM_CONNECTION_REFUSED", "Conexão ao backend recusada.")
    except UpstreamDNSError:
        return _error_response(502, "UPSTREAM_DNS_FAILURE", "Falha ao resolver o endereço do backend.")
    except UpstreamUnreachableError:
        return _error_response(502, "UPSTREAM_UNREACHABLE", "Backend inacessível.")
    except UpstreamError as exc:
        return _error_response(502, exc.error_type, str(exc))
    except Exception:
        return _error_response(502, "UPSTREAM_ERROR", "Failed to reach the upstream backend.")
    return Response(content=gateway_response.body, status_code=gateway_response.status_code, headers=gateway_response.headers)

for _method in _METHODS:
    router.add_api_route(_PATH, _gateway_entrypoint, methods=[_method])
