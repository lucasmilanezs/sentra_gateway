import logging

from src.admin.domain.ports.email_sender import EmailSenderPort

logger = logging.getLogger(__name__)


class ConsoleEmailSender(EmailSenderPort):
    async def send_verification_code(self, to_email: str, code: str) -> None:
        logger.info(
            "[email/console] código de verificação para %s: %s",
            to_email,
            code,
        )
