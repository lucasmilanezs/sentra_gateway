from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.gateway.domain.models.param import Param
from src.gateway.domain.value_objects.http_method import HttpMethod


@dataclass(frozen=True)
class Request:
    """
    Domain representation of an incoming HTTP request.

    Completely decoupled from any framework type (FastAPI, Starlette, etc.).
    The RequestParser in the interface layer is responsible for translating
    a raw framework request into this entity.

    Raw body is intentionally absent. It is opaque to the domain — no rule,
    entity, or service inspects it. It travels separately through the pipeline
    and is delivered unchanged to the proxy.
    """

    method: HttpMethod
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    params: Tuple[Param, ...] = field(default_factory=tuple)
    host: str = ""
