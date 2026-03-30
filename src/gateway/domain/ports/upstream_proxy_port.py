from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict


@dataclass
class UpstreamResponse:
    """
    Response received from the upstream backend service.

    Defined in the port so both the use case (consumer) and the
    infrastructure adapter (producer) share the same contract without
    either depending on a concrete HTTP client type.
    """

    status_code: int
    headers: Dict[str, str]
    body: bytes


class UpstreamProxyPort(ABC):
    """
    Outbound port for HTTP request forwarding to upstream backends.

    Abstracts the underlying HTTP client (httpx, aiohttp, etc.) so
    the domain and application layers are never coupled to a transport
    implementation. Swapping the client requires only a new adapter.
    """

    @abstractmethod
    async def forward(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        query_params: Dict[str, str],
    ) -> UpstreamResponse:
        """Forwards a request to the given URL and returns the response."""
        ...
