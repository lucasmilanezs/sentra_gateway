from dataclasses import dataclass
from typing import Dict

import httpx


_HOP_BY_HOP = {
    "connection", "keep-alive", "transfer-encoding",
    "te", "trailers", "upgrade",
    "proxy-authorization", "proxy-authenticate",
}


@dataclass
class ProxyResponse:
    status_code: int
    headers: Dict[str, str]
    body: bytes


class HttpProxy:
    """
    Único componente que fala com o mundo externo via HTTP.
    Recebe uma URL já resolvida e encaminha o request.

    O cliente httpx é injetado — permite reuso de connection pool
    e facilita mock em testes.
    """

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def forward(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        query_params: Dict[str, str],
    ) -> ProxyResponse:
        filtered = {k: v for k, v in headers.items()
                    if k.lower() not in _HOP_BY_HOP}

        response = await self._client.request(
            method=method,
            url=url,
            headers=filtered,
            content=body,
            params=query_params,
            follow_redirects=False,
        )

        return ProxyResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )