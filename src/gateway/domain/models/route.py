from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    """
    Entidade central do gateway.
    Relaciona um tenant_slug ao seu backend upstream.
    Imutável por design — não muda em runtime.
    """

    tenant_slug: str
    backend_url: str

    def build_upstream_url(self, path: str) -> str:
        """
        Constrói a URL completa para encaminhamento.
        O path já chega sem o prefixo do tenant.

        Exemplo:
            backend_url = "http://localhost:9000"
            path        = "usuarios/42"
            resultado   = "http://localhost:9000/usuarios/42"
        """
        clean_path = path.lstrip("/")
        base = self.backend_url.rstrip("/")
        return f"{base}/{clean_path}" if clean_path else base