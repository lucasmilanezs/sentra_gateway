from fastapi import Request as FastAPIRequest

from src.gateway.domain.models.request import Request
from src.gateway.domain.models.param import Param
from src.gateway.domain.value_objects.http_method import HttpMethod
from src.shared.http.headers import Headers
from src.shared.http.params import Params

_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
])


class RequestParser:
    def parse(self, fastapi_request: FastAPIRequest) -> Request:
        method = HttpMethod(fastapi_request.method.upper())
        path = fastapi_request.url.path
        headers = self._filter_headers(dict(fastapi_request.headers))
        query_params = dict(fastapi_request.query_params)
        params = self._extract_path_params(dict(fastapi_request.path_params))
        host = fastapi_request.headers.get("host", "")

        # Se não há x-forwarded-for na requisição (caso mais comum: cliente conecta
        # diretamente ao gateway sem proxy reverso na frente), injeta o IP da conexão
        # TCP como x-forwarded-for para que o LogEventBuilder consiga lê-lo.
        if "x-forwarded-for" not in headers and fastapi_request.client:
            headers = {**headers, "x-forwarded-for": fastapi_request.client.host}

        return Request(
            method=method,
            path=path,
            headers=Headers(headers),
            query_params=Params(query_params),
            params=params,
            host=host,
        )

    def _filter_headers(self, headers: dict) -> dict:
        return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}

    def _extract_path_params(self, path_params: dict) -> tuple:
        return tuple(Param(name=k, value=v) for k, v in path_params.items())
