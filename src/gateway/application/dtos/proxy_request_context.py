from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ProxyRequestContext:
    """
    Contexto de uma requisição já parseada pela interface.
    
    A camada de interface é responsável por extrair e popular isso.
    O use case não sabe nada sobre FastAPI, HTTP ou Request objects.
    """

    tenant_slug: str
    upstream_path: str
    method: str
    headers: Dict[str, str]
    body: bytes
    query_params: Dict[str, str]