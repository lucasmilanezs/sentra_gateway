from abc import ABC, abstractmethod


class RateLimitPort(ABC):
    """Outbound port for atomic rate limit checking."""

    @abstractmethod
    async def is_allowed(
        self,
        *,
        tenant_id: str,
        route_id: str,
        client_ip: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """Increments a scoped counter and returns True if it remains within limit."""
        ...
