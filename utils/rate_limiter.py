"""Per-site token-ish rate limiter. Thread-safe, simple delay enforcement."""
import threading
import time


class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, delay_between_requests: float = 0.0):
        self.min_interval = max(60.0 / requests_per_minute if requests_per_minute else 0.0,
                                delay_between_requests)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            sleep_for = self.min_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last = time.monotonic()
