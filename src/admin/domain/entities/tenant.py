from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    domain: str | None
    created_at: datetime
    updated_at: datetime
