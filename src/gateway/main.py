from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.infrastructure.persistence.in_memory_route_repository import InMemoryRouteRepository
from src.gateway.infrastructure.proxy.http_proxy import HttpProxy
from src.gateway.interface.http.routers.gateway_router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    O httpx.AsyncClient é criado uma vez no startup e fechado
    no shutdown — garantindo reuso de connection pool durante
    toda a vida da aplicação.
    """
    http_client = httpx.AsyncClient()

    route_repository = InMemoryRouteRepository()
    proxy = HttpProxy(client=http_client)
    forward_request = ForwardRequest(
        route_repository=route_repository,
        proxy=proxy,
    )

    app.state.forward_request = forward_request

    yield

    await http_client.aclose()


app = FastAPI(
    title="Sentra Gateway",
    lifespan=lifespan,
)

app.include_router(router)