from dataclasses import dataclass, field
from typing import Tuple

from src.gateway.domain.models.param import Param
from src.gateway.domain.value_objects.http_method import HttpMethod
from src.shared.http.headers import Headers
from src.shared.http.params import Params


@dataclass(frozen=True)
class Request:
    method: HttpMethod
    path: str
    headers: Headers
    query_params: Params
    params: Tuple[Param, ...] = field(default_factory=tuple)
    host: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.headers, Headers):
            object.__setattr__(self, "headers", Headers(self.headers))
        if not isinstance(self.query_params, Params):
            object.__setattr__(self, "query_params", Params(self.query_params))
