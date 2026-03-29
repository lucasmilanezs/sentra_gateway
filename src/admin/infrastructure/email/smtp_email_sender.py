import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.admin.domain.ports.email_sender import EmailSenderPort

logger = logging.getLogger(__name__)


class SmtpEmailSender(EmailSenderPort):
    def __init__(
        self,
        host: str,
        port: int,
        user: str | None,
        password: str | None,
        mail_from: str,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._mail_from = mail_from

    def _send_sync(self, to_email: str, code: str) -> None:
        msg = MIMEMultipart()
        msg["Subject"] = "Sentra Admin — código de verificação"
        msg["From"] = self._mail_from
        msg["To"] = to_email
        body = f"Seu código de verificação é: {code}\n\nEle expira em poucos minutos."
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            smtp.starttls()
            if self._user and self._password:
                smtp.login(self._user, self._password)
            smtp.sendmail(self._mail_from, [to_email], msg.as_string())

    async def send_verification_code(self, to_email: str, code: str) -> None:
        await asyncio.to_thread(self._send_sync, to_email, code)
        logger.info("[email/smtp] código enviado para %s", to_email)
