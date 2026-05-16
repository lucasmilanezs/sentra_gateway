from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GatewayTenant:
    """Representação mínima de tenant necessária ao data plane."""
    id: str
    domain: str | None


class TenantRepository(ABC):
    """
    Outbound port para resolução de tenant por domínio HTTP.

    O gateway usa o Host header para identificar a qual tenant
    pertence a requisição antes de fazer qualquer resolução de rota.
    """

    @abstractmethod
    async def get_by_domain(self, host: str) -> Optional[GatewayTenant]:
        """
        Retorna o tenant cujo domain bate com o host recebido,
        ou None se nenhum tenant estiver registrado para aquele host.
        """
        ...