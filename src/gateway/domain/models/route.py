from dataclasses import dataclass, field
from typing import Tuple

from src.gateway.domain.value_objects.http_method import HttpMethod


@dataclass(frozen=True)
class Route:
    """
    Maps an incoming request path to a backend Domain.

    Registered and managed by the admin plane.
    The gateway resolves routes at request time using longest-prefix matching:
    the route whose path_prefix best (most specifically) matches the incoming
    path wins. Ties in length are broken by insertion order.

    Single-tenant design: there is no tenant_slug in the URL. Routing is
    purely path-based against all registered routes.
    """

    id: str
    tenant_id: str
    path_prefix: str
    domain_id: str
    methods: Tuple[HttpMethod, ...] = field(default_factory=tuple)

    def matches(self, path: str, method: str) -> bool:
        """
        Returns True if this route matches the given path and HTTP method.

        Path matching rules:
          - Exact match: path == path_prefix
          - Prefix match: path starts with path_prefix followed by "/"
          - Wildcard: path_prefix == "/" matches everything
        """
        prefix = self.path_prefix.rstrip("/")
        path_ok = (
            path == self.path_prefix
            or path.startswith(prefix + "/")
            or self.path_prefix == "/"
        )
        method_ok = (
            not self.methods
            or HttpMethod(method.upper()) in self.methods
        )
        return path_ok and method_ok

    def strip_prefix(self, path: str) -> str:
        """
        Returns the path with this route's prefix stripped.

        The result is the upstream-relative path passed to the backend.
        Always returns at least "/" so the backend receives a valid path.

        Example:
            Route(path_prefix="/api").strip_prefix("/api/users/42") → "/users/42"
            Route(path_prefix="/api").strip_prefix("/api")          → "/"
        """
        prefix = self.path_prefix.rstrip("/")
        if path.startswith(prefix):
            remainder = path[len(prefix):]
            return remainder if remainder else "/"
        return path
