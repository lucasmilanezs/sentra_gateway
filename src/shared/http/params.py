from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping


class Params(Mapping[str, str]):
    """Normalized query parameter collection used by policy rules."""

    def __init__(self, values: Mapping[str, str] | Iterable[str] | None = None) -> None:
        self._values: dict[str, str] = {}
        if values is None:
            return
        if isinstance(values, Mapping):
            for key, value in values.items():
                normalized = self.normalize_name(key)
                self._values[normalized] = str(value)
            return
        for name in values:
            normalized = self.normalize_name(name)
            self._values[normalized] = ""

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = (name or "").strip()
        if not normalized:
            raise ValueError("param não pode ser vazio")
        if any(ch.isspace() for ch in normalized):
            raise ValueError(f"param inválido: {name}")
        return normalized

    @classmethod
    def from_names(cls, values: Iterable[str] | None) -> "Params":
        return cls(values or [])

    def contains(self, name: str) -> bool:
        return self.normalize_name(name) in self._values

    def to_list(self) -> list[str]:
        return list(self._values.keys())

    def to_dict(self) -> dict[str, str]:
        return dict(self._values)

    def __getitem__(self, key: str) -> str:
        return self._values[self.normalize_name(key)]

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(self.normalize_name(key), default)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __bool__(self) -> bool:
        return bool(self._values)
