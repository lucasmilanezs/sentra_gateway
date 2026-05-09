import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

CHANNEL = "sentra:config:updated"


class RedisPublisher:
    """
    Publishes configuration change notifications to the gateway via Redis pub/sub.

    Called after any write operation that affects gateway behavior
    (route create/update/delete, policy create/update/delete).
    The gateway subscriber receives the message and reloads its snapshot.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def notify_config_updated(self) -> None:
        try:
            await self._client.publish(CHANNEL, "updated")
            logger.info("Notificação de atualização de configuração publicada.")
        except Exception as exc:
            # Publicação é best-effort — falha não deve interromper a operação
            logger.warning("Falha ao publicar notificação Redis: %s", exc)