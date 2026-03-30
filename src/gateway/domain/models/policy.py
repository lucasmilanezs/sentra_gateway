from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class Policy:
    """
    Security and control policy attached to a Route.

    Defined in the admin plane, evaluated by the gateway on every request.
    The gateway reads policies as configuration — it never writes them.

    Evaluation is fail-closed: if any check fails, the request is denied.
    Routes without an associated policy allow all requests through.
    """

    id: str
    route_id: str
    requires_auth: bool = False
    rate_limit_per_minute: Optional[int] = None
    allowed_roles: Tuple[str, ...] = field(default_factory=tuple)
