from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tenant:
    id: str
    name: str
    alias: str
    created_at: datetime
    updated_at: datetime
