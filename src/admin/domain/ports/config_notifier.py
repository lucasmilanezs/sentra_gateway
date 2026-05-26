from __future__ import annotations

from typing import Protocol


class ConfigNotifier(Protocol):
    """Port used by admin use cases to announce configuration changes.

    The application layer depends on this abstraction only. Concrete delivery
    mechanisms, such as Redis pub/sub, belong to infrastructure.
    """

    async def notify_config_updated(self) -> None:
        ...
