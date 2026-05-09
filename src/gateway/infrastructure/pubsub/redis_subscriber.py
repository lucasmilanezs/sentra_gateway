import asyncio
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

CHANNEL = "sentra:config:updated"


async def listen_for_config_updates(redis_url: str, on_update) -> None:
    """
    Escuta o canal Redis em loop permanente.
    Quando o Admin publicar no canal, chama on_update() que recarrega
    o snapshot do Postgres sem reiniciar o gateway.
    Reconecta automaticamente em caso de queda do Redis.
    """
    while True:
        client = None
        try:
            client = aioredis.from_url(redis_url)
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL)
            logger.info("Gateway inscrito no canal Redis: %s", CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                logger.info(
                    "Atualização de configuração recebida — recarregando snapshot."
                )
                try:
                    await on_update()
                    logger.info("Snapshot recarregado com sucesso.")
                except Exception as exc:
                    logger.error("Falha ao recarregar snapshot: %s", exc)

        except asyncio.CancelledError:
            # Shutdown limpo — gateway encerrando
            logger.info("Subscriber Redis encerrado.")
            break
        except Exception as exc:
            logger.warning(
                "Conexão Redis perdida (%s) — reconectando em 5s.", exc
            )
            await asyncio.sleep(5)
        finally:
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass