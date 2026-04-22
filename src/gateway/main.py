import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.infrastructure.config.settings import GatewaySettings
from src.gateway.infrastructure.observability.file_log_writer import FileLogWriter
from src.gateway.infrastructure.persistence.postgres_snapshot import (
    PostgresSnapshotRepository,
)
from src.gateway.infrastructure.proxy.httpx_upstream_proxy import HttpxUpstreamProxy
from src.gateway.interface.http.routers.gateway_router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = GatewaySettings()

    # Carrega snapshot de rotas do Postgres
    snapshot = PostgresSnapshotRepository()
    await snapshot.load(settings.database_url)

    http_client = httpx.AsyncClient()

    forward_request = ForwardRequest(
        route_repository=snapshot,
        domain_repository=snapshot,
        policy_repository=snapshot,
        proxy=HttpxUpstreamProxy(client=http_client),
        log_port=FileLogWriter(log_path=Path(settings.log_path)),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    app.state.forward_request = forward_request

    logger.info(
        "Gateway iniciado. DB: %s:%s", settings.postgres_host, settings.postgres_port
    )

    yield

    await http_client.aclose()


app = FastAPI(
    title="Sentra Gateway",
    description="Data plane — receives, inspects, and forwards HTTP requests.",
    lifespan=lifespan,
)

app.include_router(router)