from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import urlparse

from src.admin.domain.exceptions import ValidationError
from src.admin.domain.value_objects.http_method import HttpMethod

_PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9/_\-{}]*$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_DISPLAY_COLOR = "#2dd4bf"


@dataclass
class AdminRoute:
    """Managed route in the admin plane."""

    id: str
    tenant_id: str
    path_pattern: str
    methods: list[HttpMethod]
    backend_url: str
    display_color: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.path_pattern = self.normalize_path_pattern(self.path_pattern)
        self.methods = self.normalize_methods(self.methods)
        self.backend_url = self.normalize_backend_url(self.backend_url)
        self.display_color = self.normalize_display_color(self.display_color)

    @classmethod
    def create(
        cls,
        *,
        id: str,
        tenant_id: str,
        path_pattern: str,
        methods: list[str] | list[HttpMethod],
        backend_url: str,
        now: datetime,
        display_color: str | None = None,
    ) -> "AdminRoute":
        return cls(
            id=id,
            tenant_id=tenant_id,
            path_pattern=path_pattern,
            methods=methods,
            backend_url=backend_url,
            display_color=display_color or DEFAULT_DISPLAY_COLOR,
            created_at=now,
            updated_at=now,
        )

    def with_updates(self, *, data: dict, now: datetime) -> "AdminRoute":
        return AdminRoute(
            id=self.id,
            tenant_id=self.tenant_id,
            path_pattern=data.get("path_pattern", self.path_pattern),
            methods=data.get("methods", self.methods),
            backend_url=data.get("backend_url", self.backend_url),
            display_color=data.get("display_color", self.display_color),
            created_at=self.created_at,
            updated_at=now,
        )

    def audit_summary(self) -> str:
        return self.path_pattern

    def audit_detail(self, *, changed_fields: list[str] | None = None) -> dict:
        detail = {
            "methods": [m.value for m in self.methods],
            "backend_url": self.backend_url,
            "display_color": self.display_color,
        }
        if changed_fields is not None:
            detail["changed_fields"] = sorted(changed_fields)
        return detail

    @staticmethod
    def normalize_path_pattern(path_pattern: str) -> str:
        value = (path_pattern or "").strip()
        if not value.startswith("/"):
            raise ValidationError("path_pattern deve começar com /")
        if "//" in value:
            raise ValidationError("path_pattern não pode conter //")
        if " " in value:
            raise ValidationError("path_pattern não pode conter espaços")
        if value != value.lower():
            raise ValidationError("path_pattern deve usar apenas letras minúsculas (REST)")
        if not _PATH_RE.match(value):
            raise ValidationError("path_pattern inválido: use letras minúsculas, números, /, -, _ ou parâmetros {id}")
        return value

    @staticmethod
    def normalize_backend_url(backend_url: str) -> str:
        value = (backend_url or "").strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("backend_url deve ser uma URL http(s) válida")
        return value

    @staticmethod
    def normalize_methods(raw: list[str] | list[HttpMethod]) -> list[HttpMethod]:
        result: list[HttpMethod] = []
        for method in raw or []:
            if isinstance(method, HttpMethod):
                parsed = method
            else:
                try:
                    parsed = HttpMethod(str(method).upper())
                except ValueError as exc:
                    raise ValidationError(f"método HTTP inválido: {method}") from exc
            if parsed not in result:
                result.append(parsed)
        if not result:
            raise ValidationError("pelo menos um método HTTP deve ser informado")
        return result

    @staticmethod
    def normalize_display_color(display_color: str | None) -> str:
        value = (display_color or DEFAULT_DISPLAY_COLOR).strip()
        if not value:
            return DEFAULT_DISPLAY_COLOR
        if not _COLOR_RE.match(value):
            raise ValidationError("display_color deve estar no formato hexadecimal #RRGGBB")
        return value.lower()
