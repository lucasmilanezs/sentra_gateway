from abc import ABC, abstractmethod

from src.gateway.domain.models.log_event import LogEvent


class LogPort(ABC):
    """
    Outbound port for operational log writing.

    Decouples the log destination (file, stdout, remote sink) from the
    gateway pipeline. Failures in log writing must not affect the critical
    path — implementations are responsible for silent degradation.
    """

    @abstractmethod
    async def write(self, event: LogEvent) -> None:
        """Persists a log event to the configured destination."""
        ...
