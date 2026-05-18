from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime



@dataclass
class DomainPolicy:
    """
    Política global vinculada a um TenantDomain.

    Funciona como fallback: aplicada a qualquer rota do tenant
    que não possua uma Policy individual configurada.
    Relação 1-to-1 com TenantDomain.
    """

    id: str
    domain_id: str
    requires_auth: bool = False
    rate_limit_per_minute: int | None = None
    allowed_roles: list[str] = field(default_factory=list)
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_clock_skew_seconds: int = 30
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
