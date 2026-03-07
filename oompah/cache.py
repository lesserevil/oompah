"""Simple TTL cache for API responses."""

from __future__ import annotations

import time
import threading
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with per-key TTL.

    Usage:
        cache = TTLCache()
        cache.set("key", value, ttl_ms=5000)
        result = cache.get("key")  # returns value or None if expired
        cache.invalidate("key")    # explicit invalidation
        cache.invalidate_prefix("issues")  # invalidate all keys starting with prefix
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_ms: int) -> None:
        expires_at = time.monotonic() + ttl_ms / 1000.0
        with self._lock:
            self._store[key] = (value, expires_at)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
