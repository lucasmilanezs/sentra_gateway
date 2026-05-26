import asyncio
import logging
from contextlib import asynccontextmanager
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI

from src.gateway.application.use_cases.apply_policy_pipeline import ApplyPolicyPipeline
from src.gateway.application.use_cases.forward_request import ForwardRequest
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker
from src.gateway.infrastructure.config.settings import GatewaySettings
from src.gateway.domain.services.audit_event_builder import AuditEventBuilder
from src.gateway.infrastructure.observability.redis_log_writer import RedisLogWriter
from src.gateway.infrastructure.observability.postgres_audit_writer import PostgresAuditWriter
from src.gateway.infrastructure.persistence.postgres_snapshot import (
    PostgresSnapshotRepository,
)
from src.gateway.infrastructure.proxy.httpx_upstream_proxy import HttpxUpstreamProxy
from src.gateway.infrastructure.pubsub.redis_subscriber import listen_for_config_updates
from src.gateway.infrastructure.redis.rate_limiter import RateLimiter
from src.gateway.interface.http.routers.gateway_router import router as gateway_router
from src.gateway.interface.http.routers.health_router import router as health_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = GatewaySettings()

    snapshot = PostgresSnapshotRepository()
    await snapshot.load(settings.database_url)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)

    jwt_secret = settings.jwt_secret or None
    policy_pipeline = ApplyPolicyPipeline(
        policy_evaluator=PolicyEvaluator(
            jwt_secret=jwt_secret,
            jwt_algorithms=(settings.jwt_algorithm,),
        ),
        rate_limit_checker=RateLimitChecker(
            port=RateLimiter(client=redis_client)
        ),
    )

    log_writer = RedisLogWriter(
        client=redis_client,
        retention_days=settings.raw_log_retention_days,
        max_entries_per_tenant_per_day=settings.raw_log_max_entries_per_tenant_per_day,
        redact_headers=settings.raw_log_redact_header_names,
    )

    audit_writer = None
    if settings.audit_to_postgres:
        audit_writer = PostgresAuditWriter(settings.database_url)

    http_client = httpx.AsyncClient()

    forward_request = ForwardRequest(
        route_repository=snapshot,
        domain_repository=snapshot,
        policy_repository=snapshot,
        proxy=HttpxUpstreamProxy(client=http_client),
        log_port=log_writer,
        policy_pipeline=policy_pipeline,
        log_event_builder=LogEventBuilder(),
        tenant_repository=snapshot,
        audit_port=audit_writer,
        audit_event_builder=AuditEventBuilder(),
    )

    app.state.forward_request = forward_request
    app.state.snapshot = snapshot
    app.state.settings = settings

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
    if audit_writer is not None:
        await audit_writer.dispose()


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
app.include_router(health_router)
app.include_router(gateway_router)
