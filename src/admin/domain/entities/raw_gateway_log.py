from __future__ import annotations

from dataclasses import dataclass, field
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
    tenant_label: str | None = None
    route_label: str | None = None
    policy_summary: str | None = None
    header_checks: list[dict[str, Any]] = field(default_factory=list)
    param_checks: list[dict[str, Any]] = field(default_factory=list)
    policy_checks: list[dict[str, Any]] = field(default_factory=list)
    layer_errors: dict[str, Any] = field(default_factory=dict)
