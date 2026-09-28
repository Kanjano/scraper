"""Proxy pool with round-robin rotation.

Reads `PROXY_LIST` (comma-separated) when `USE_PROXY=True`. Accepts entries as:
    host:port
    user:pass@host:port
    http://user:pass@host:port
    socks5://host:port
Scheme defaults to http when omitted. Exposes the current proxy in both
`requests` and Playwright shapes.
"""
import threading
from urllib.parse import urlparse

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize(entry: str) -> str:
    entry = entry.strip()
    if "://" not in entry:
        entry = "http://" + entry
    return entry


class ProxyManager:
    def __init__(self, proxies: list[str] | None = None, enabled: bool | None = None):
        raw = proxies if proxies is not None else settings.proxies
        self.enabled = settings.use_proxy if enabled is None else enabled
        self._proxies = [_normalize(p) for p in raw if p.strip()]
        self._idx = 0
        self._lock = threading.Lock()
        if self.enabled and not self._proxies:
            logger.warning("USE_PROXY=True but PROXY_LIST is empty — proxies disabled")
            self.enabled = False

    @property
    def active(self) -> bool:
        return self.enabled and bool(self._proxies)

    def next_proxy(self) -> str | None:
        """Round-robin the next proxy URL, or None when disabled."""
        if not self.active:
            return None
        with self._lock:
            proxy = self._proxies[self._idx % len(self._proxies)]
            self._idx += 1
            return proxy

    def as_requests(self, proxy_url: str | None = None) -> dict | None:
        """Dict for `requests`: {'http': url, 'https': url}."""
        url = proxy_url or self.next_proxy()
        if not url:
            return None
        return {"http": url, "https": url}

    @staticmethod
    def as_playwright(proxy_url: str | None) -> dict | None:
        """Dict for Playwright launch: {server, username, password}."""
        if not proxy_url:
            return None
        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server += f":{parsed.port}"
        out = {"server": server}
        if parsed.username:
            out["username"] = parsed.username
        if parsed.password:
            out["password"] = parsed.password
        return out


# Shared default pool.
proxy_manager = ProxyManager()
