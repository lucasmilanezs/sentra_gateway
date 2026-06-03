from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis

from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import (
    classify_connection_error,
    parse_redis_endpoint,
    safe_redis_url,
    tcp_probe,
)

logger = logging.getLogger(__name__)

CHANNEL = "sentra:config:updated"


async def listen_for_config_updates(
    redis_url: str,
    on_update: Callable[[], Awaitable[Any]],
    *,
    status_registry: DependencyStatusRegistry | None = None,
    status_name: str = "redis_pubsub",
    channel: str = CHANNEL,
    max_retries: int = 5,
    connect_timeout_seconds: float = 1.0,
    operation_timeout_seconds: float = 1.5,
    idle_ping_seconds: float = 20.0,
) -> None:
    """
    Listen for Admin configuration updates and reload the gateway snapshot.

    Redis Pub/Sub is a reactive invalidation channel. It stays idle most of the
    time, so the subscriber performs a lightweight Redis PING only after an idle
    window without messages. If Redis disappears, the task retries a bounded
    number of times, marks Pub/Sub as inactive and stops. A later successful
    Redis health probe can start a fresh subscriber task from the gateway app.
    """
    attempt = 0
    backoff_seconds = 1.0
    endpoint = parse_redis_endpoint(redis_url)
    safe_url = safe_redis_url(redis_url)
    max_retries = max(1, int(max_retries))
    idle_ping_seconds = max(1.0, float(idle_ping_seconds))

    while True:
        client = None
        pubsub = None
        try:
            attempt += 1
            if status_registry:
                status_registry.mark_degraded(
                    status_name,
                    "tentando conectar ao Redis Pub/Sub",
                    reason_code="connecting",
                    phase="tcp_probe",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    reconnect_attempt=attempt,
                    max_retries=max_retries,
                )

            await tcp_probe(endpoint.host, endpoint.port, timeout=connect_timeout_seconds)

            client = aioredis.from_url(
                redis_url,
                socket_connect_timeout=connect_timeout_seconds,
                socket_timeout=operation_timeout_seconds,
                health_check_interval=30,
                retry_on_timeout=False,
            )
            await client.ping()

            pubsub = client.pubsub()
            await pubsub.subscribe(channel)
            attempt = 0
            backoff_seconds = 1.0
            logger.info("Gateway subscribed to Redis channel %s (%s).", channel, safe_url)
            if status_registry:
                status_registry.mark_ok(
                    status_name,
                    "inscrito no canal Redis de atualização de configuração",
                    reason_code="subscribed",
                    phase="listening",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    retry_policy="bounded_reactivated_by_health_ping",
                    max_retries=max_retries,
                    idle_ping_seconds=idle_ping_seconds,
                )

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=idle_ping_seconds)
                if message is None:
                    await client.ping()
                    if status_registry:
                        status_registry.mark_ok(
                            status_name,
                            "canal Pub/Sub ocioso; Redis respondeu ao PING de manutenção",
                            reason_code="idle_ping_ok",
                            phase="listening",
                            channel=channel,
                            redis_url=safe_url,
                            idle_ping_seconds=idle_ping_seconds,
                        )
                    continue

                if message.get("type") != "message":
                    continue

                logger.info("Configuration update received; reloading gateway snapshot.")
                try:
                    await on_update()
                    logger.info("Gateway snapshot reloaded successfully.")
                    if status_registry:
                        status_registry.mark_ok(
                            status_name,
                            "snapshot recarregada após evento Redis Pub/Sub",
                            reason_code="update_received",
                            phase="listening",
                            channel=channel,
                            redis_url=safe_url,
                        )
                except Exception as exc:
                    logger.exception("Failed to reload gateway snapshot after Redis update.")
                    if status_registry:
                        reason_code, human_reason = classify_connection_error(exc)
                        status_registry.mark_error(
                            "snapshot_reload",
                            exc,
                            detail="falha ao recarregar snapshot após evento Redis Pub/Sub",
                            reason_code=reason_code,
                            human_reason=human_reason,
                            phase="snapshot_reload",
                        )

        except asyncio.CancelledError:
            logger.info("Redis subscriber shutdown requested.")
            if status_registry:
                status_registry.mark_degraded(status_name, "subscriber encerrado", reason_code="shutdown", phase="shutdown")
            break
        except Exception as exc:
            reason_code, human_reason = classify_connection_error(exc)
            remaining = max(max_retries - attempt, 0)
            if status_registry:
                # Pub/Sub is usually the first component to notice a Redis outage.
                # Propagate that information to the shared Redis connectivity flag
                # so request-path adapters can short-circuit immediately instead of
                # paying Redis DNS/socket timeouts until /health runs again.
                status_registry.mark_error(
                    "redis_ping",
                    exc,
                    detail=human_reason,
                    reason_code=reason_code,
                    human_reason=human_reason,
                    phase="detected_by_pubsub",
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    retry_in_seconds=backoff_seconds,
                )
                for component, detail in {
                    "redis_rate_limit": "Rate limit degradado porque o Pub/Sub detectou indisponibilidade geral do Redis. O gateway opera em fail-open sem tocar no Redis no caminho crítico.",
                    "redis_raw_logs": "Logs operacionais degradados porque o Pub/Sub detectou indisponibilidade geral do Redis. A auditoria persistente não é afetada.",
                }.items():
                    state = status_registry.get(component)
                    if state.status not in {"inactive", "error"}:
                        status_registry.mark_degraded(
                            component,
                            detail,
                            reason_code=reason_code,
                            human_reason=human_reason,
                            phase="redis_connectivity_unavailable",
                        )
                status_registry.mark_error(
                    status_name,
                    exc,
                    detail=(
                        f"{human_reason}; nova tentativa em {backoff_seconds:.1f}s "
                        f"({remaining} tentativa(s) restante(s))"
                    ),
                    reason_code=reason_code,
                    human_reason=human_reason,
                    phase="connect_subscribe_or_idle_ping",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    reconnect_attempt=attempt,
                    max_retries=max_retries,
                    retry_in_seconds=backoff_seconds,
                )
            logger.warning(
                "Redis Pub/Sub unavailable [%s/%s] at %s (attempt %s/%s). %s; retrying in %.1fs.",
                reason_code,
                type(exc).__name__,
                safe_url,
                attempt,
                max_retries,
                human_reason,
                backoff_seconds,
            )
            if attempt >= max_retries:
                message = (
                    "Redis Pub/Sub inativo após esgotar as tentativas. "
                    "O gateway continua servindo com a última snapshot carregada. "
                    "A próxima resposta OK do Redis no healthcheck reativará a mensageria."
                )
                logger.error("%s Last failure: [%s] %s", message, type(exc).__name__, exc)
                if status_registry:
                    status_registry.mark_inactive(
                        status_name,
                        message,
                        reason_code="retry_budget_exhausted",
                        human_reason=human_reason,
                        phase="inactive",
                        channel=channel,
                        redis_url=safe_url,
                        redis_host=endpoint.host,
                        redis_port=endpoint.port,
                        reconnect_attempt=attempt,
                        max_retries=max_retries,
                        last_failure_type=type(exc).__name__,
                        last_failure=str(exc),
                    )
                break
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30.0)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception:
                    logger.debug("Error while closing Redis Pub/Sub.", exc_info=True)
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    logger.debug("Error while closing Redis subscriber client.", exc_info=True)
