from abc import ABC, abstractmethod


class EmailSenderPort(ABC):
    @abstractmethod
    async def send_verification_code(self, to_email: str, code: str) -> None:
        """Envia código de verificação (ex.: recuperação de senha)."""
        ...
