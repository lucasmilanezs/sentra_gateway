from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis

from src.shared.runtime.dependency_status import DependencyStatusRegistry
from src.shared.runtime.redis_diagnostics import classify_connection_error, parse_redis_endpoint, safe_redis_url

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
    idle_ping_seconds: float = 20.0,
    connect_timeout_seconds: float = 1.0,
    operation_timeout_seconds: float = 1.5,
) -> None:
    """
    Listen for Admin config updates and reload the gateway snapshot.

    This task is the only long-lived Redis watcher in the gateway. It does not
    continuously probe Redis while healthy. It waits for Pub/Sub messages and,
    if the channel stays idle for ``idle_ping_seconds``, performs a lightweight
    PING to ensure the connection is still alive.

    If Redis disappears, the gateway keeps serving with the last loaded
    snapshot. Reconnection is bounded; after the retry budget is exhausted the
    subscriber is marked inactive and stops trying until the process restarts.
    """
    endpoint = parse_redis_endpoint(redis_url)
    safe_url = safe_redis_url(redis_url)
    max_retries = max(1, int(max_retries))
    idle_ping_seconds = max(1.0, float(idle_ping_seconds))
    connect_timeout_seconds = max(0.2, float(connect_timeout_seconds))
    operation_timeout_seconds = max(0.2, float(operation_timeout_seconds))

    attempt = 0
    backoff_seconds = 1.0

    while True:
        client: aioredis.Redis | None = None
        pubsub = None
        try:
            attempt += 1
            if status_registry:
                status_registry.mark_degraded(
                    status_name,
                    "conectando ao canal Redis de atualização de configuração",
                    reason_code="connecting",
                    phase="connect",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    reconnect_attempt=attempt,
                    max_retries=max_retries,
                )

            client = aioredis.from_url(
                redis_url,
                socket_connect_timeout=connect_timeout_seconds,
                socket_timeout=operation_timeout_seconds,
                health_check_interval=None,
                retry_on_timeout=False,
            )
            await client.ping()
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)

            attempt = 0
            backoff_seconds = 1.0
            logger.info("Gateway subscribed to Redis config channel %s (%s).", channel, safe_url)
            if status_registry:
                status_registry.mark_ok(
                    status_name,
                    "mensageria Redis conectada e aguardando atualizações",
                    reason_code="subscribed",
                    phase="listening",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    idle_ping_seconds=idle_ping_seconds,
                    max_retries=max_retries,
                )

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=idle_ping_seconds)
                if message is None:
                    # The channel is allowed to be quiet. This ping is only a
                    # liveness assertion after an idle window, not polling for
                    # business state.
                    await client.ping()
                    if status_registry:
                        status_registry.mark_ok(
                            status_name,
                            "mensageria Redis conectada; canal sem eventos recentes",
                            reason_code="idle_ping_ok",
                            phase="listening",
                            channel=channel,
                            redis_url=safe_url,
                            redis_host=endpoint.host,
                            redis_port=endpoint.port,
                            idle_ping_seconds=idle_ping_seconds,
                        )
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
                            redis_host=endpoint.host,
                            redis_port=endpoint.port,
                        )
                except Exception as exc:
                    logger.warning("Failed to reload gateway snapshot after Redis update [%s]: %s", type(exc).__name__, exc)
                    if status_registry:
                        status_registry.mark_error(
                            "snapshot_reload",
                            exc,
                            detail="falha ao recarregar snapshot após evento Redis Pub/Sub",
                            reason_code="snapshot_reload_failed",
                            phase="snapshot_reload",
                        )

        except asyncio.CancelledError:
            logger.info("Redis subscriber shutdown requested.")
            if status_registry:
                status_registry.mark_degraded(status_name, "subscriber encerrado", reason_code="shutdown", phase="shutdown")
            break
        except Exception as exc:
            reason_code, human_reason = classify_connection_error(exc)
            if status_registry:
                status_registry.mark_error(
                    status_name,
                    exc,
                    detail=f"{human_reason}; tentativa {attempt}/{max_retries}",
                    reason_code=reason_code,
                    human_reason=human_reason,
                    phase="connect_or_listen",
                    channel=channel,
                    redis_url=safe_url,
                    redis_host=endpoint.host,
                    redis_port=endpoint.port,
                    reconnect_attempt=attempt,
                    max_retries=max_retries,
                    retry_in_seconds=backoff_seconds if attempt < max_retries else None,
                )
            logger.warning(
                "Redis Pub/Sub unavailable [%s/%s] at %s (attempt %s/%s): %s",
                reason_code,
                type(exc).__name__,
                safe_url,
                attempt,
                max_retries,
                human_reason,
            )
            if attempt >= max_retries:
                detail = (
                    "mensageria Redis inativa após esgotar tentativas; gateway segue usando "
                    "a última snapshot carregada com sucesso"
                )
                if status_registry:
                    status_registry.mark_inactive(
                        status_name,
                        detail,
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
                logger.error("%s. Last failure [%s]: %s", detail, type(exc).__name__, exc)
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
