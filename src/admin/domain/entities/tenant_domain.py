from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.admin.domain.exceptions import ValidationError


@dataclass
class TenantDomain:
    """Inbound host/domain bound to a tenant."""

    id: str
    tenant_id: str
    domain: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.domain = self.normalize_domain(self.domain)

    @classmethod
    def create(cls, *, id: str, tenant_id: str, domain: str, now: datetime) -> "TenantDomain":
        return cls(id=id, tenant_id=tenant_id, domain=domain, created_at=now, updated_at=now)

    @staticmethod
    def normalize_domain(domain: str) -> str:
        normalized = (domain or "").strip().lower()
        if not normalized:
            raise ValidationError("domain não pode ser vazio")
        if "://" in normalized or "/" in normalized or any(ch.isspace() for ch in normalized):
            raise ValidationError("domain deve ser um host/subdomain, não uma URL completa")
        return normalized

    def audit_summary(self) -> str:
        return self.domain

    def audit_detail(self) -> dict:
        return {"domain": self.domain}
