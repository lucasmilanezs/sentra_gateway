import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI

from src.gateway.application.use_cases.apply_policy_pipeline import ApplyPolicyPipeline
from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker
from src.gateway.infrastructure.config.settings import GatewaySettings
from src.gateway.infrastructure.observability.file_log_writer import FileLogWriter
from src.gateway.infrastructure.persistence.postgres_snapshot import (
    PostgresSnapshotRepository,
)
from src.gateway.infrastructure.proxy.httpx_upstream_proxy import HttpxUpstreamProxy
from src.gateway.infrastructure.pubsub.redis_subscriber import listen_for_config_updates
from src.gateway.infrastructure.redis.rate_limiter import RateLimiter
from src.gateway.interface.http.routers.gateway_router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = GatewaySettings()

    snapshot = PostgresSnapshotRepository()
    await snapshot.load(settings.database_url)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)

    policy_pipeline = ApplyPolicyPipeline(
        policy_evaluator=PolicyEvaluator(),
        rate_limit_checker=RateLimitChecker(
            port=RateLimiter(client=redis_client)
        ),
    )

    http_client = httpx.AsyncClient()

    forward_request = ForwardRequest(
        route_repository=snapshot,
        domain_repository=snapshot,
        policy_repository=snapshot,
        proxy=HttpxUpstreamProxy(client=http_client),
        log_port=FileLogWriter(log_path=Path(settings.log_path)),
        policy_pipeline=policy_pipeline,
        log_event_builder=LogEventBuilder(),
        tenant_repository=snapshot,
    )

    app.state.forward_request = forward_request

    subscriber_task = asyncio.create_task(
        listen_for_config_updates(
            redis_url=settings.redis_url,
            on_update=lambda: snapshot.reload(settings.database_url),
        )
    )

    logger.info(
        "Gateway iniciado. DB: %s:%s | Redis: %s:%s",
        settings.postgres_host,
        settings.postgres_port,
        settings.redis_host,
        settings.redis_port,
    )

    yield

    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass

    await http_client.aclose()
    await redis_client.aclose()


app = FastAPI(
    title="Sentra Gateway",
    description="Data plane — receives, inspects, and forwards HTTP requests.",
    lifespan=lifespan,
)

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.include_router(router)
