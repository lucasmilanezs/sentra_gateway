from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import get_wiring, require_permission

router = APIRouter(tags=["raw-logs"])


@router.get("/logs/raw")
async def list_raw_gateway_logs(
    claims: Annotated[JwtClaims, Depends(require_permission("audit"))],
    wiring=Depends(get_wiring),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Exposes the gateway JSONL operational log for the Admin UI.

    Audit records remain the curated semantic view in PostgreSQL. This endpoint is
    intentionally raw and reads the aggregated JSON lines file produced by the
    gateway FileLogWriter. Superuser may filter by tenant_id; admins/members are
    always restricted to their own tenant scope.
    """
    path = Path(wiring.settings.gateway_log_path)
    effective_tenant = tenant_id if claims.role == "superuser" else claims.tenant_id

    if not path.exists():
        return {"items": [], "total": 0, "log_path": str(path)}

    # Tail-read enough lines for UI use without loading very large files entirely.
    lines = await _read_tail_lines(path, max_lines=max(limit * 5, 500))
    items: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            record = {"timestamp": None, "outcome": "MALFORMED_LOG_LINE", "raw": line}

        if effective_tenant and record.get("tenant_id") != effective_tenant:
            continue

        record["summary"] = _summarize(record)
        items.append(record)
        if len(items) >= limit:
            break

    return {"items": items, "total": len(items), "log_path": str(path)}


async def _read_tail_lines(path: Path, *, max_lines: int) -> list[str]:
    # Synchronous file IO is acceptable here because the endpoint is admin-only and
    # limited; keeping it local avoids introducing extra infrastructure.
    import asyncio

    return await asyncio.to_thread(_read_tail_lines_sync, path, max_lines)


def _read_tail_lines_sync(path: Path, max_lines: int) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return lines[-max_lines:]


def _summarize(record: dict) -> str:
    method = record.get("method") or "?"
    path = record.get("path") or "?"
    status = record.get("status_code") or "?"
    outcome = record.get("outcome") or "UNKNOWN"
    route_id = record.get("route_id") or "no-route"
    return f"{method} {path} → {status} · {outcome} · {str(route_id)[:8]}"
