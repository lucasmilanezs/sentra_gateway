from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ProxyRequestContext:
    """
    Contexto de uma requisição já parseada pela interface.
    
    Body deliberadamente ausente — é opaco ao domínio e à aplicação.
    Não há regra, entidade ou decisão que dependa dele.
    Ele vive na interface e desce direto para o proxy.
    """

    tenant_slug: str
    upstream_path: str
    method: str
    headers: Dict[str, str]
    query_params: Dict[str, str]