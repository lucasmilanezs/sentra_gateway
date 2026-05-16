from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.gateway.domain.models.param import Param
from src.gateway.domain.value_objects.http_method import HttpMethod


@dataclass(frozen=True)
class Request:
    method: HttpMethod
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    params: Tuple[Param, ...] = field(default_factory=tuple)
    host: str = ""
