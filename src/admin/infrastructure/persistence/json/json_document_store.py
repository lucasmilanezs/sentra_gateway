import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_dt(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat()


class JsonDocumentStore:
    """Armazenamento transacional simples em um único arquivo JSON (dev / sem Postgres)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def _default_document(self) -> dict[str, Any]:
        return {
            "tenants": [],
            "routes": [],
            "users": [],
            "password_resets": {},
        }

    def _read_unlocked(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._default_document()
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return self._default_document()
        data = json.loads(raw)
        for key in ("tenants", "routes", "users"):
            if key not in data:
                data[key] = []
        if "password_resets" not in data:
            data["password_resets"] = {}
        return data

    def _write_unlocked(self, doc: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def write(self, doc: dict[str, Any]) -> None:
        with self._lock:
            self._write_unlocked(doc)

    def mutate(self, fn: Any) -> None:
        with self._lock:
            doc = self._read_unlocked()
            fn(doc)
            self._write_unlocked(doc)

    async def read_async(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.read)

    async def mutate_async(self, fn: Any) -> None:
        await asyncio.to_thread(self.mutate, fn)


__all__ = ["JsonDocumentStore", "_parse_dt", "_serialize_dt"]
