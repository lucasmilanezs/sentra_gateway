from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    tenant_id: str | None
    created_at: datetime
    updated_at: datetime
    role: str = "admin"
