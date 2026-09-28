"""Simple TTL in-memory cache for search results."""
import threading
import time

from config.settings import settings


class CacheManager:
    def __init__(self, ttl_hours: int | None = None):
        self.ttl = (ttl_hours if ttl_hours is not None else settings.cache_ttl_hours) * 3600
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self.enabled = settings.cache_enabled

    def get(self, key: str):
        if not self.enabled:
            return None
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, value = item
            if time.time() - ts > self.ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


cache = CacheManager()
