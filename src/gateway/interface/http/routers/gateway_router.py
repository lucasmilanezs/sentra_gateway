from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from src.gateway.application.dtos.proxy_request_context import ProxyRequestContext
from src.gateway.application.use_cases.forward_request import (
    ForwardRequest,
    RouteNotFoundError,
)
from src.gateway.interface.schema.error_response import ErrorResponse

router = APIRouter()


async def gateway_entrypoint(
    tenant_slug: str,
    path: str,
    request: Request,
) -> Response:
    use_case: ForwardRequest = request.app.state.forward_request

    context = ProxyRequestContext(
        tenant_slug=tenant_slug,
        upstream_path=path,
        method=request.method,
        headers=dict(request.headers),
        body=await request.body(),
        query_params=dict(request.query_params),
    )

    try:
        proxy_response = await use_case.execute(context)
    except RouteNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code="TENANT_NOT_FOUND",
                message=f"Tenant '{tenant_slug}' não encontrado.",
            ).model_dump(),
        )

    return Response(
        content=proxy_response.body,
        status_code=proxy_response.status_code,
        headers=proxy_response.headers,
    )


_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
_PATH = "/{tenant_slug}/{path:path}"

for method in _METHODS:
    router.add_api_route(
        _PATH,
        gateway_entrypoint,
        methods=[method],
    )