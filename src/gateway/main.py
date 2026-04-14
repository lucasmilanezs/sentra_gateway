from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.infrastructure.observability.file_log_writer import FileLogWriter
from src.gateway.infrastructure.persistence.in_memory_domain_repository import (
    InMemoryDomainRepository,
)
from src.gateway.infrastructure.persistence.in_memory_policy_repository import (
    InMemoryPolicyRepository,
)
from src.gateway.infrastructure.persistence.in_memory_route_repository import (
    InMemoryRouteRepository,
)
from src.gateway.infrastructure.proxy.httpx_upstream_proxy import HttpxUpstreamProxy
from src.gateway.interface.http.routers.gateway_router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Composition root — wires all dependencies and manages their lifecycle.

    Infrastructure instances are created once at startup and injected into
    use cases via constructor injection. FastAPI app.state is the single
    handoff point between the lifespan context and the request handlers.

    Shutdown: the shared httpx.AsyncClient is closed gracefully, releasing
    all pooled connections before the process exits.
    """
    http_client = httpx.AsyncClient()

    forward_request = ForwardRequest(
        route_repository=InMemoryRouteRepository(),
        domain_repository=InMemoryDomainRepository(),
        policy_repository=InMemoryPolicyRepository(),
        proxy=HttpxUpstreamProxy(client=http_client),
        log_port=FileLogWriter(log_path=Path("logs/gateway.log")),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    app.state.forward_request = forward_request

    yield

    await http_client.aclose()


app = FastAPI(
    title="Sentra Gateway",
    description="Data plane — receives, inspects, and forwards HTTP requests.",
    lifespan=lifespan,
)

app.include_router(router)
