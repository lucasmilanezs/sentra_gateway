from typing import Dict

import httpx

from src.gateway.domain.ports.upstream_proxy_port import UpstreamProxyPort, UpstreamResponse


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


class HttpxUpstreamProxy(UpstreamProxyPort):
    """
    Implements UpstreamProxyPort using httpx.AsyncClient.

    The client is injected at construction time so that:
      - A single connection pool is reused across all requests (startup).
      - Tests can inject a mock or HTTPX transport without network I/O.

    Hop-by-hop headers (RFC 7230 §6.1) are stripped before forwarding
    to prevent proxying connection-level metadata to the upstream.
    Redirects are not followed — the upstream response is returned as-is
    so the gateway does not silently alter the request lifecycle.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def forward(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        query_params: Dict[str, str],
    ) -> UpstreamResponse:
        filtered_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in _HOP_BY_HOP
        }

        response = await self._client.request(
            method=method,
            url=url,
            headers=filtered_headers,
            content=body,
            params=query_params,
            follow_redirects=False,
        )

        return UpstreamResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )
