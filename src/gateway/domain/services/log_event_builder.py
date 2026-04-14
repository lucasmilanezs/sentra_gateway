from datetime import datetime, timezone
from typing import Optional

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.models.request import Request


class LogEventBuilder:
    """
    Domain service that constructs LogEvent instances.

    Centralises log event creation so that timestamp generation,
    field mapping, and any future enrichment live in one place,
    keeping the use case free of formatting concerns.
    """

    def build(
        self,
        request: Request,
        upstream_url: str,
        status_code: int,
        latency_ms: float,
        route_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> LogEvent:
        return LogEvent(
            timestamp=datetime.now(tz=timezone.utc),
            method=request.method.value,
            path=request.path,
            upstream_url=upstream_url,
            status_code=status_code,
            latency_ms=latency_ms,
            route_id=route_id,
            error=error,
        )
