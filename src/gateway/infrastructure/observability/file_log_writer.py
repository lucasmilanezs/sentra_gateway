import asyncio
import json
from pathlib import Path

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort


class FileLogWriter(LogPort):
    """
    Writes operational log events to a line-delimited JSON (NDJSON) file.

    Each event is appended as a single JSON line, making the log trivially
    parseable by tools such as jq, Filebeat, or any log aggregator.

    File I/O runs in a thread-pool via asyncio.to_thread so it never blocks
    the event loop. A lock serialises concurrent writes within the same process.

    The parent directory is created on first write if it does not exist.
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._lock = asyncio.Lock()

    async def write(self, event: LogEvent) -> None:
        record = {
            "timestamp": event.timestamp.isoformat(),
            "method": event.method,
            "path": event.path,
            "upstream_url": event.upstream_url,
            "status_code": event.status_code,
            "latency_ms": round(event.latency_ms, 2),
            "route_id": event.route_id,
            "error": event.error,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)
