from abc import ABC, abstractmethod


class RateLimitPort(ABC):
    """
    Outbound port for atomic rate limit checking.

    Implementations use a backing store (Redis) to increment and
    inspect a counter per key within a time window.
    """

    @abstractmethod
    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Increments the counter for key and returns True if within limit.
        Sets expiration on first increment. Atomic by design.
        """
        ...