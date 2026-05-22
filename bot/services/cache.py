from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._items: dict[str, _Entry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._items.get(key)
        if not entry:
            return None
        if entry.expires_at < time.time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._items[key] = _Entry(value=value, expires_at=time.time() + self._ttl)

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        v = self.get(key)
        if v is not None:
            return v
        v = factory()
        self.set(key, v)
        return v

    def invalidate(self, key: str) -> None:
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()

