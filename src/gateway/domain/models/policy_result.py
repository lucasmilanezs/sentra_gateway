from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PolicyResult:
    """
    Immutable outcome of a policy evaluation.

    When allowed is False, status_code and reason are set so the
    use case can return a meaningful denial response without any
    knowledge of what specific check failed.
    """

    allowed: bool
    status_code: int = 200
    reason: Optional[str] = None
