from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.admin.domain.entities.admin_change_event import AdminChangeEvent


class AdminChangeEventBuilder:
    @staticmethod
    def build(
        *,
        tenant_id: str | None,
        actor_id: str,
        actor_role: str,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_summary: str,
        detail: dict[str, Any] | str | None = None,
    ) -> AdminChangeEvent:
        if isinstance(detail, dict):
            detail_text = json.dumps(detail, ensure_ascii=False, default=str)
        else:
            detail_text = detail
        return AdminChangeEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_summary=resource_summary,
            timestamp=datetime.now(timezone.utc),
            detail=detail_text,
        )
