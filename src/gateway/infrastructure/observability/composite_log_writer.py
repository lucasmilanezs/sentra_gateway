from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort


class CompositeLogWriter(LogPort):
    """Writes log events to multiple backends (file + Postgres audit)."""

    def __init__(self, *writers: LogPort) -> None:
        self._writers = writers

    async def write(self, event: LogEvent) -> None:
        for writer in self._writers:
            try:
                await writer.write(event)
            except Exception:
                pass
