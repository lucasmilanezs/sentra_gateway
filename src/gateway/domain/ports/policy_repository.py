from abc import ABC, abstractmethod
from typing import Optional

from src.gateway.domain.models.policy import Policy


class PolicyRepository(ABC):
    """
    Outbound port for policy retrieval.

    The gateway reads the policy associated with a matched route before
    forwarding. Returning None means no policy is configured for that route
    and the PolicyEvaluator will allow the request through.
    """

    @abstractmethod
    async def get_by_route_id(self, route_id: str) -> Optional[Policy]:
        """Returns the Policy for the given route_id, or None if not found."""
        ...
