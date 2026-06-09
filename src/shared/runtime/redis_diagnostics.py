from __future__ import annotations

import asyncio
import errno
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

try:
    import redis.exceptions as redis_exceptions
except Exception:  # pragma: no cover
    redis_exceptions = None  # type: ignore


@dataclass(frozen=True)
class RedisEndpoint:
    url: str
    host: str
    port: int


def safe_redis_url(redis_url: str) -> str:
    if "://" not in redis_url or "@" not in redis_url:
        return redis_url
    scheme, rest = redis_url.split("://", 1)
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


def parse_redis_endpoint(redis_url: str) -> RedisEndpoint:
    parsed = urlparse(redis_url)
    return RedisEndpoint(
        url=safe_redis_url(redis_url),
        host=parsed.hostname or "redis",
        port=int(parsed.port or 6379),
    )


def _iter_causes(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def classify_connection_error(exc: BaseException) -> tuple[str, str]:
    for cause in _iter_causes(exc):
        if isinstance(cause, socket.gaierror):
            return "dns_resolution_failed", "o nome do host Redis não pôde ser resolvido pela rede Docker"
        if isinstance(cause, ConnectionRefusedError):
            return "connection_refused", "o host Redis respondeu, mas recusou a conexão TCP"
        if isinstance(cause, TimeoutError) or isinstance(cause, asyncio.TimeoutError):
            return "connection_timeout", "o Redis não respondeu dentro do tempo limite configurado"
        if isinstance(cause, OSError):
            if cause.errno == errno.ECONNREFUSED:
                return "connection_refused", "o host Redis respondeu, mas recusou a conexão TCP"
            if cause.errno in {errno.EHOSTUNREACH, errno.ENETUNREACH}:
                return "network_unreachable", "a rede Docker não conseguiu alcançar o host Redis"
            if cause.errno == errno.ECONNRESET:
                return "connection_reset", "a conexão com Redis foi encerrada durante a operação"
    if redis_exceptions is not None:
        if isinstance(exc, getattr(redis_exceptions, "TimeoutError", ())):
            return "connection_timeout", "o Redis não respondeu dentro do tempo limite configurado"
        if isinstance(exc, getattr(redis_exceptions, "ConnectionError", ())):
            return "connection_error", "falha de conexão com Redis"
    return "connection_error", "falha de conexão com Redis"


def _blocking_tcp_probe(host: str, port: int, timeout: float) -> None:
    # Use a blocking socket in a worker thread instead of asyncio.open_connection.
    # uvloop/asyncio DNS failures may otherwise leave cancelled resolver futures that
    # are later reported as "Future exception was never retrieved". The health
    # path needs to be cheap, deterministic and fully contained.
    with socket.create_connection((host, port), timeout=timeout):
        return


async def tcp_probe(host: str, port: int, *, timeout: float = 1.0) -> None:
    await asyncio.to_thread(_blocking_tcp_probe, host, port, max(0.1, float(timeout)))
