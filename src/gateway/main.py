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
from src.gateway.infrastructure.persistence.postgres_snapshot import PostgresSnapshotRepository
from src.gateway.infrastructure.proxy.httpx_upstream_proxy import HttpxUpstreamProxy
from src.gateway.infrastructure.pubsub.redis_subscriber import listen_for_config_updates
from src.gateway.infrastructure.redis.rate_limiter import RateLimiter
from src.gateway.interface.http.routers.gateway_router import router as gateway_router
from src.gateway.interface.http.routers.health_router import router as health_router
from src.shared.runtime.dependency_status import DependencyStatusRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _redis_client(
    redis_url: str,
    *,
    decode_responses: bool = False,
    connect_timeout_seconds: float = 1.0,
    operation_timeout_seconds: float = 1.5,
) -> aioredis.Redis:
    return aioredis.from_url(
        redis_url,
        decode_responses=decode_responses,
        socket_connect_timeout=connect_timeout_seconds,
        socket_timeout=operation_timeout_seconds,
        health_check_interval=30,
        retry_on_timeout=False,
    )


async def _ping_redis(client: aioredis.Redis, registry: DependencyStatusRegistry, name: str) -> None:
    try:
        await client.ping()
        registry.mark_ok(name, "Redis respondeu ao PING de inicialização.", reason_code="startup_ping_ok", phase="startup")
    except Exception as exc:
        registry.mark_error(name, exc, detail="Redis indisponível na inicialização; o componente iniciará em modo degradado e será atualizado quando for usado.", phase="startup")
        logger.warning("Redis dependency %s is unavailable at startup [%s]: %s", name, type(exc).__name__, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = GatewaySettings()
    dependency_status = DependencyStatusRegistry()
    app.state.dependency_status = dependency_status

    snapshot = PostgresSnapshotRepository(policy_secret_key=settings.policy_secret_key)
    try:
        logger.info("Loading gateway snapshot from Postgres %s:%s...", settings.postgres_host, settings.postgres_port)
        await snapshot.load(settings.database_url)
        dependency_status.mark_ok(
            "snapshot",
            "snapshot loaded",
            routes_loaded=snapshot.route_count(),
            tenants_loaded=snapshot.tenant_count(),
            policies_loaded=snapshot.policy_count(),
            loaded_at=snapshot.loaded_at.isoformat() if snapshot.loaded_at else None,
            last_successful_load_at=snapshot.loaded_at.isoformat() if snapshot.loaded_at else None,
        )
    except Exception as exc:
        dependency_status.mark_error("snapshot", exc, detail="failed to load snapshot during gateway startup")
        logger.exception("Failed to load gateway snapshot during startup.")
        raise

    redis_rate_limit_client = _redis_client(
        settings.redis_url,
        decode_responses=False,
        connect_timeout_seconds=settings.redis_connect_timeout_seconds,
        operation_timeout_seconds=settings.redis_operation_timeout_seconds,
    )
    redis_log_client = _redis_client(
        settings.redis_url,
        decode_responses=False,
        connect_timeout_seconds=settings.redis_connect_timeout_seconds,
        operation_timeout_seconds=settings.redis_operation_timeout_seconds,
    )
    await _ping_redis(redis_rate_limit_client, dependency_status, "redis_rate_limit")
    await _ping_redis(redis_log_client, dependency_status, "redis_raw_logs")

    policy_pipeline = ApplyPolicyPipeline(
        policy_evaluator=PolicyEvaluator(),
        rate_limit_checker=RateLimitChecker(
            port=RateLimiter(
                client=redis_rate_limit_client,
                fail_open=settings.redis_fail_open,
                status_registry=dependency_status,
                max_failures=settings.redis_runtime_max_failures,
            )
        ),
    )

    log_writer = RedisLogWriter(
        client=redis_log_client,
        retention_days=settings.raw_log_retention_days,
        max_entries_per_tenant_per_day=settings.raw_log_max_entries_per_tenant_per_day,
        redact_headers=settings.raw_log_redact_header_names,
        status_registry=dependency_status,
        max_failures=settings.redis_runtime_max_failures,
    )

    audit_writer = None
    if settings.audit_to_postgres:
        audit_writer = PostgresAuditWriter(
            settings.database_url,
            status_registry=dependency_status,
        )
        dependency_status.mark_ok(
            "postgres_audit",
            "Auditoria persistente configurada; aguardando o primeiro evento para confirmar escrita no PostgreSQL.",
            reason_code="audit_writer_configured",
            phase="idle",
        )
    else:
        dependency_status.mark_ok(
            "postgres_audit",
            "Auditoria persistente desativada por configuração.",
            reason_code="audit_disabled",
            phase="disabled",
            enabled=False,
        )

    http_client = httpx.AsyncClient()

    async def reload_snapshot() -> None:
        await snapshot.reload(settings.database_url)
        dependency_status.mark_ok(
            "snapshot",
            "snapshot reloaded",
            routes_loaded=snapshot.route_count(),
            tenants_loaded=snapshot.tenant_count(),
            policies_loaded=snapshot.policy_count(),
            loaded_at=snapshot.loaded_at.isoformat() if snapshot.loaded_at else None,
            last_successful_load_at=snapshot.loaded_at.isoformat() if snapshot.loaded_at else None,
        )

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
    app.state.redis_rate_limit_client = redis_rate_limit_client
    app.state.redis_log_client = redis_log_client

    def _new_subscriber_task(reason: str) -> asyncio.Task:
        logger.info("Starting Redis Pub/Sub subscriber (%s).", reason)
        dependency_status.mark_degraded(
            "redis_pubsub",
            f"iniciando subscriber Redis Pub/Sub ({reason})",
            reason_code="subscriber_starting",
            phase="starting",
        )
        return asyncio.create_task(
            listen_for_config_updates(
                redis_url=settings.redis_url,
                on_update=reload_snapshot,
                status_registry=dependency_status,
                max_retries=settings.redis_subscriber_max_retries,
                connect_timeout_seconds=settings.redis_connect_timeout_seconds,
                operation_timeout_seconds=settings.redis_operation_timeout_seconds,
                idle_ping_seconds=settings.redis_pubsub_idle_ping_seconds,
            )
        )

    async def restart_redis_subscriber_if_needed(reason: str = "redis health recovered") -> bool:
        current = getattr(app.state, "subscriber_task", None)
        current_status = dependency_status.status_of("redis_pubsub")
        if current is not None and not current.done():
            return False
        if current_status not in {"inactive", "error", "unknown", "degraded"}:
            return False
        app.state.subscriber_task = _new_subscriber_task(reason)
        return True

    app.state.restart_redis_subscriber_if_needed = restart_redis_subscriber_if_needed
    subscriber_task = _new_subscriber_task("startup")
    app.state.subscriber_task = subscriber_task

    logger.info(
        "Gateway iniciado. DB: %s:%s | Redis: %s:%s | Redis fail-open: %s",
        settings.postgres_host,
        settings.postgres_port,
        settings.redis_host,
        settings.redis_port,
        settings.redis_fail_open,
    )

    try:
        yield
    finally:
        subscriber_task = getattr(app.state, "subscriber_task", None)
        if subscriber_task is not None:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        await http_client.aclose()
        await redis_rate_limit_client.aclose()
        await redis_log_client.aclose()
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
