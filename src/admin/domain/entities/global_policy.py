from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GlobalPolicy:
    """
    Política de segurança global vinculada a um tenant.

    Funciona como fallback: aplicada a qualquer rota do tenant
    que não possua uma Policy individual configurada.
    Relação 1-to-1 com Tenant.
    """

    id: str
    tenant_id: str
    requires_auth: bool = False
    rate_limit_per_minute: int | None = None
    allowed_roles: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)