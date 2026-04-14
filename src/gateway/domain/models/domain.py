from dataclasses import dataclass

from src.gateway.domain.value_objects.backend_url import BackendUrl


@dataclass(frozen=True)
class Domain:
    """
    Represents a registered backend service (upstream).

    Created and managed exclusively by the admin plane.
    The gateway treats it as read-only configuration: it resolves
    a Domain from a Route and uses its backend_url to forward requests.

    Immutable by design — domains do not change during a request lifecycle.
    """

    id: str
    name: str
    backend_url: BackendUrl
