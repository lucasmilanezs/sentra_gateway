from typing import Dict, Tuple

from fastapi import Request as FastAPIRequest

from src.gateway.domain.models.param import Param
from src.gateway.domain.models.request import Request
from src.gateway.domain.value_objects.http_method import HttpMethod


_HOP_BY_HOP = frozenset({
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailers",
    "upgrade",
    "proxy-authorization",
    "proxy-authenticate",
})


class RequestParser:
    """
    Translates a raw FastAPI Request into a domain Request entity.

    Single responsibility: boundary translation at the interface layer.
    No business logic, no I/O — only format conversion.

    Hop-by-hop headers are stripped here, at the outermost layer,
    before the request enters the domain pipeline. This follows the
    principle that connection-level metadata should not cross the
    proxy boundary (RFC 7230 §6.1).
    """

    def parse(self, fastapi_request: FastAPIRequest) -> Request:
        method = HttpMethod(fastapi_request.method.upper())
        path = fastapi_request.url.path
        headers = self._filter_headers(dict(fastapi_request.headers))
        query_params = dict(fastapi_request.query_params)
        params = self._extract_path_params(dict(fastapi_request.path_params))
        host = fastapi_request.headers.get("host", "")

        return Request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            params=params,
            host=host,
        )

    def _filter_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {
            k: v for k, v in headers.items()
            if k.lower() not in _HOP_BY_HOP
        }

    def _extract_path_params(self, path_params: Dict[str, str]) -> Tuple[Param, ...]:
        return tuple(Param(name=k, value=v) for k, v in path_params.items())
