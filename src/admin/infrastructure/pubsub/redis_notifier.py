from __future__ import annotations

import logging

import redis.asyncio as aioredis

from src.admin.domain.ports.config_notifier import ConfigNotifier

logger = logging.getLogger(__name__)

CHANNEL = "sentra:config:updated"


class RedisConfigNotifier(ConfigNotifier):
    """Redis pub/sub adapter for gateway configuration update notifications."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def notify_config_updated(self) -> None:
        try:
            await self._client.publish(CHANNEL, "updated")
            logger.info("Notificação de atualização de configuração publicada.")
        except Exception as exc:
            # Best-effort: a notification failure must not rollback the admin write.
            logger.warning("Falha ao publicar notificação Redis: %s", exc)
