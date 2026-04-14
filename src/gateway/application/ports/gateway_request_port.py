from abc import ABC, abstractmethod

from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.domain.models.request import Request


class GatewayRequestPort(ABC):
    """
    Inbound port — the contract through which the interface layer drives
    the gateway application.

    This is the only entry point known to the interface. It accepts a
    domain Request (already parsed from HTTP) plus the raw body bytes,
    and returns a GatewayResponse that the interface translates to HTTP.

    ForwardRequest implements this port. The separation allows swapping
    use-case orchestration (e.g. adding circuit-breaking or A/B routing)
    without touching the HTTP adapter.
    """

    @abstractmethod
    async def handle(self, request: Request, raw_body: bytes) -> GatewayResponse:
        ...
