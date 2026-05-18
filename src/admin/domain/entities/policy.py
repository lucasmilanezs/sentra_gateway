from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Policy:
    """
    Política de segurança vinculada a uma rota do gateway.

    Relação 1-to-1 com AdminRoute: cada rota tem zero ou uma política.
    Campos None/False/vazio significam ausência do controle — o gateway
    passa a requisição sem aplicar aquela verificação.
    """

    id: str
    route_id: str
    requires_auth: bool = False
    rate_limit_per_minute: int | None = None
    allowed_roles: list[str] = field(default_factory=list)
    jwt_validate_exp: bool = True
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_clock_skew_seconds: int = 30
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)