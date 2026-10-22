from __future__ import annotations


class NameTable:
    def __init__(self, names: dict[str, int] | None = None):
        self._names: dict[str, int] = {}
        self._ids: dict[int, str] = {}
        for name, name_id in (names or {}).items():
            if not isinstance(name, str) or not isinstance(name_id, int) or name_id < 0:
                raise ValueError("name table entries must map strings to non-negative integers")
            if name in self._names or name_id in self._ids:
                raise ValueError("name table names and IDs must be unique")
            self._names[name] = name_id
            self._ids[name_id] = name

    def intern(self, name: str) -> int:
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        existing = self._names.get(name)
        if existing is not None:
            return existing
        name_id = max(self._ids, default=-1) + 1
        self._names[name] = name_id
        self._ids[name_id] = name
        return name_id

    def lookup(self, name_id: int) -> str:
        return self._ids[name_id]

    def to_dict(self) -> dict[str, int]:
        return dict(self._names)

    @classmethod
    def from_dict(cls, names: dict[str, int]) -> NameTable:
        return cls(names)


__all__ = ["NameTable"]
