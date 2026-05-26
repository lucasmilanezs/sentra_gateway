from dataclasses import dataclass
from datetime import datetime


@dataclass
class AdminChangeEvent:
    id: str
    tenant_id: str | None
    actor_id: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    resource_summary: str
    timestamp: datetime
    detail: str | None = None
    tenant_label: str | None = None
    actor_label: str | None = None
    resource_label: str | None = None
