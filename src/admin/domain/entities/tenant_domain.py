from dataclasses import dataclass
from datetime import datetime


@dataclass
class TenantDomain:
    """
    Domain de entrada vinculado a um tenant.

    Cada tenant pode ter múltiplos domains/subdomains.
    O gateway usa o Host header para resolver qual tenant
    está sendo acessado consultando esta entidade.

    Relação 1-to-1 opcional com DomainPolicy (política global
    aplicada a todas as rotas do tenant que não tenham policy própria).
    """

    id: str
    tenant_id: str
    domain: str
    created_at: datetime
    updated_at: datetime
