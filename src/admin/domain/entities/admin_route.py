from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


from src.admin.domain.value_objects.http_method import HttpMethod


@dataclass
class AdminRoute:
    """
    Rota administrada (cadastro no plano admin), distinta do modelo do data plane.

    methods: lista de métodos HTTP aceitos por esta rota. O gateway rejeita
    requisições cujo método não esteja na lista. Lista vazia significa
    que todos os métodos são aceitos (comportamento permissivo).
    """

    id: str
    tenant_id: str
    path_pattern: str
    methods: list[HttpMethod]
    backend_url: str
    created_at: datetime
    updated_at: datetime
