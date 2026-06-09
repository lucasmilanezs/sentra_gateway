from typing import Dict
import httpx
from src.gateway.domain.exceptions import (
    UpstreamConnectionRefusedError, UpstreamDNSError,
    UpstreamTimeoutError, UpstreamUnreachableError,
)
from src.gateway.domain.ports.upstream_proxy_port import UpstreamProxyPort, UpstreamResponse

_HOP_BY_HOP = frozenset({"connection","keep-alive","transfer-encoding","te","trailers","upgrade","proxy-authorization","proxy-authenticate"})

class HttpxUpstreamProxy(UpstreamProxyPort):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def forward(self, method: str, url: str, headers: Dict[str, str], body: bytes, query_params: Dict[str, str]) -> UpstreamResponse:
        filtered_headers = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}
        try:
            response = await self._client.request(method=method, url=url, headers=filtered_headers, content=body, params=query_params, follow_redirects=False)
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(f"Timeout na chamada upstream: {exc}") from exc
        except httpx.ConnectError as exc:
            msg = str(exc).lower()
            if "name or service not known" in msg or "nodename nor servname" in msg:
                raise UpstreamDNSError(f"Falha de DNS: {exc}") from exc
            raise UpstreamConnectionRefusedError(f"Conexão recusada: {exc}") from exc
        except httpx.RemoteProtocolError as exc:
            raise UpstreamUnreachableError(f"Protocolo inválido: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnreachableError(f"Erro HTTP inesperado: {exc}") from exc
        return UpstreamResponse(status_code=response.status_code, headers=dict(response.headers), body=response.content)
