from dataclasses import dataclass
from datetime import datetime

from src.admin.domain.value_objects.http_method import HttpMethod


@dataclass
class AdminRoute:
    """Rota administrada (cadastro no plano admin), distinta do modelo do data plane."""

    id: str
    tenant_id: str
    path_pattern: str
    method: HttpMethod
    backend_url: str
    created_at: datetime
    updated_at: datetime
