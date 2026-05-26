import asyncio
import json
from pathlib import Path
from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort


class FileLogWriter(LogPort):
    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._lock = asyncio.Lock()

    async def write(self, event: LogEvent) -> None:
        record = {
            "timestamp": event.timestamp.isoformat(),
            "method": event.method, "path": event.path,
            "upstream_url": event.upstream_url, "status_code": event.status_code,
            "latency_ms": round(event.latency_ms, 2),
            "route_id": event.route_id, "tenant_id": event.tenant_id,
            "client_ip": event.client_ip, "error": event.error,
            "outcome": event.outcome,
            "request_headers": event.request_headers,
            "query_params": event.query_params,
            "policy_checks": event.policy_checks,
            "upstream_response_headers": event.upstream_response_headers,
            "upstream_response_body_preview": event.upstream_response_body_preview,
            "layer_errors": event.layer_errors,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)
