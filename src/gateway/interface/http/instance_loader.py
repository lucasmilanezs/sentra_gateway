from fastapi import Request as FastAPIRequest

from src.gateway.application.ports.gateway_request_port import GatewayRequestPort


class InstanceLoader:
    """
    Retrieves application use-case instances from FastAPI app state.

    Acts as the DI accessor at the interface boundary: the router calls
    this instead of importing concrete use-case classes, keeping the
    interface decoupled from application implementations.

    All instances are wired once at startup in main.py (composition root)
    and stored in app.state; this loader is the single read point.
    """

    @staticmethod
    def gateway_request_port(request: FastAPIRequest) -> GatewayRequestPort:
        return request.app.state.forward_request
