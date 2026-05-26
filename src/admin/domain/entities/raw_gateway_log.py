from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawGatewayLog:
    id: str
    timestamp: datetime | None
    tenant_id: str | None
    route_id: str | None
    method: str | None
    path: str | None
    status_code: int | None
    outcome: str
    latency_ms: float | None
    summary: str
    payload: dict[str, Any]
