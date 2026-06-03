from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DependencyStatus:
    name: str
    status: str = "unknown"
    detail: str | None = None
    reason_code: str | None = None
    phase: str | None = None
    last_error_type: str | None = None
    last_error: str | None = None
    checked_at: datetime | None = None
    last_ok_at: datetime | None = None
    first_failure_at: datetime | None = None
    last_failure_at: datetime | None = None
    disabled_at: datetime | None = None
    next_retry_at: datetime | None = None
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_ok(self, detail: str | None = None, **metadata: Any) -> None:
        now = datetime.now(timezone.utc)
        self.status = "ok"
        self.detail = detail
        self.reason_code = metadata.pop("reason_code", None)
        self.phase = metadata.pop("phase", self.phase)
        self.last_error_type = None
        self.last_error = None
        self.checked_at = now
        self.last_ok_at = now
        self.first_failure_at = None
        self.last_failure_at = None
        self.disabled_at = None
        self.next_retry_at = None
        self.attempts = 0
        if metadata:
            self.metadata.update(metadata)

    def mark_degraded(self, detail: str | None = None, **metadata: Any) -> None:
        self.status = "degraded"
        self.detail = detail
        self.reason_code = metadata.pop("reason_code", self.reason_code)
        self.phase = metadata.pop("phase", self.phase)
        self.checked_at = datetime.now(timezone.utc)
        if metadata:
            self.metadata.update(metadata)

    def mark_error(self, exc: BaseException | str, *, detail: str | None = None, **metadata: Any) -> None:
        now = datetime.now(timezone.utc)
        self.status = "error"
        self.checked_at = now
        self.last_failure_at = now
        if self.first_failure_at is None:
            self.first_failure_at = now
        self.attempts += 1
        self.reason_code = metadata.pop("reason_code", self.reason_code)
        self.phase = metadata.pop("phase", self.phase)
        retry_in_seconds = metadata.pop("retry_in_seconds", None)
        if retry_in_seconds is not None:
            try:
                self.next_retry_at = datetime.fromtimestamp(now.timestamp() + float(retry_in_seconds), tz=timezone.utc)
            except Exception:
                self.next_retry_at = None
        elif "next_retry_at" in metadata:
            raw_next = metadata.pop("next_retry_at")
            self.next_retry_at = raw_next if isinstance(raw_next, datetime) else None
        if isinstance(exc, BaseException):
            self.last_error_type = type(exc).__name__
            self.last_error = str(exc)
        else:
            self.last_error_type = "RuntimeError"
            self.last_error = exc
        self.detail = detail or self.last_error
        if metadata:
            self.metadata.update(metadata)

    def mark_inactive(self, detail: str | None = None, **metadata: Any) -> None:
        now = datetime.now(timezone.utc)
        self.status = "inactive"
        self.detail = detail or "dependency marked inactive after repeated failures"
        self.reason_code = metadata.pop("reason_code", self.reason_code or "retry_budget_exhausted")
        self.phase = metadata.pop("phase", self.phase)
        self.checked_at = now
        self.disabled_at = now
        self.next_retry_at = None
        if metadata:
            self.metadata.update(metadata)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "detail": self.detail,
            "reason_code": self.reason_code,
            "phase": self.phase,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "last_ok_at": self.last_ok_at.isoformat() if self.last_ok_at else None,
            "first_failure_at": self.first_failure_at.isoformat() if self.first_failure_at else None,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "attempts": self.attempts,
            "active": self.status != "inactive",
        }
        if self.last_error_type:
            payload["last_error_type"] = self.last_error_type
        if self.last_error:
            payload["last_error"] = self.last_error
        if self.metadata:
            payload.update(self.metadata)
        return {k: v for k, v in payload.items() if v is not None}


class DependencyStatusRegistry:
    def __init__(self) -> None:
        self._items: dict[str, DependencyStatus] = {}

    def get(self, name: str) -> DependencyStatus:
        if name not in self._items:
            self._items[name] = DependencyStatus(name=name)
        return self._items[name]

    def mark_ok(self, name: str, detail: str | None = None, **metadata: Any) -> None:
        self.get(name).mark_ok(detail, **metadata)

    def mark_degraded(self, name: str, detail: str | None = None, **metadata: Any) -> None:
        self.get(name).mark_degraded(detail, **metadata)

    def mark_error(self, name: str, exc: BaseException | str, *, detail: str | None = None, **metadata: Any) -> None:
        self.get(name).mark_error(exc, detail=detail, **metadata)

    def mark_inactive(self, name: str, detail: str | None = None, **metadata: Any) -> None:
        self.get(name).mark_inactive(detail, **metadata)

    def is_inactive(self, name: str) -> bool:
        return self.get(name).status == "inactive"

    def status_of(self, name: str) -> str:
        return self.get(name).status

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {name: status.as_dict() for name, status in sorted(self._items.items())}

    def overall(self, critical: tuple[str, ...] = ()) -> str:
        if not self._items:
            return "unknown"
        for name in critical:
            if self.get(name).status != "ok":
                return "error"
        if any(item.status == "error" for item in self._items.values()):
            return "degraded"
        if any(item.status in {"degraded", "unknown", "inactive"} for item in self._items.values()):
            return "degraded"
        return "ok"
