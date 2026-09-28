"""Abstract base class all site scrapers inherit from."""
import time
from abc import ABC, abstractmethod

import requests

from scrapers.parsers import parse_price as _parse_price
from scrapers.validator import is_valid, normalize
from utils.currency_converter import converter
from utils.logger import get_logger
from utils.proxy_manager import proxy_manager
from utils.rate_limiter import RateLimiter


def _fix_encoding(resp: requests.Response) -> None:
    """requests falls back to ISO-8859-1 when a text/html reply declares no
    charset, which garbles Shift_JIS/EUC-JP shops. Sniff the body instead."""
    if "charset=" not in (resp.headers.get("content-type") or "").lower():
        sniffed = getattr(resp, "apparent_encoding", None)  # curl_cffi has none
        if sniffed:
            resp.encoding = sniffed


class BaseScraper(ABC):
    def __init__(self, site_config: dict):
        self.config = site_config
        self.name = site_config["name"]
        self.currency = site_config.get("currency", "EUR")
        self.timeout = site_config.get("timeout", 30)
        self.max_retries = site_config.get("max_retries", 3)
        rl = site_config.get("rate_limit", {})
        self.rate_limiter = RateLimiter(
            requests_per_minute=rl.get("requests_per_minute", 10),
            delay_between_requests=rl.get("delay_between_requests", 0),
        )
        if site_config.get("impersonate"):
            # Edge anti-bot (Cloudflare bot score, Akamai) fingerprints TLS/HTTP2
            # before any JS runs; curl_cffi sends Chrome's exact handshake. Its own
            # Chrome headers must stay: a foreign User-Agent breaks the disguise.
            from curl_cffi import requests as curl_requests

            self.session = curl_requests.Session(impersonate="chrome")
            self.session.headers.update({"Accept-Language": "en-US,en;q=0.9"})
        else:
            self.session = requests.Session()
            self.session.headers.update(site_config.get("headers", {}))
        # One-off request that puts the shop session in the right state, e.g.
        # Guitar Salon picks the display currency from the visitor's IP.
        setup = site_config.get("session_setup")
        if setup:
            try:
                self.session.post(setup["url"], data=setup.get("data"), timeout=self.timeout)
            except Exception as exc:  # noqa: BLE001
                get_logger("scraper.setup").warning("session setup failed: %s", exc)
        self.proxy_manager = proxy_manager
        self.logger = get_logger(f"scraper.{site_config.get('name', 'base')}")
        self.last_error: str | None = None

    # ------- abstract surface -------
    @abstractmethod
    def search(self, query: str, **kwargs) -> list[dict]:
        ...

    @abstractmethod
    def get_product_details(self, product_url: str) -> dict:
        ...

    def parse_price(self, price_str: str) -> float | None:
        return _parse_price(price_str)

    # ------- shared helpers -------
    def convert_to_eur(self, amount: float, from_currency: str) -> float:
        return converter.to_base(amount, from_currency)

    def retry_with_backoff(self, func, *args, **kwargs):
        delay = 1.0
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.logger.warning(
                    "attempt %d/%d failed: %s", attempt, self.max_retries, exc
                )
                time.sleep(delay)
                delay *= 2
        # Scrapers log and swallow this and return no offers; keep it so callers
        # can tell a failed shop from one that simply has nothing to offer.
        self.last_error = f"{type(last_exc).__name__}: {last_exc}"[:200]
        raise last_exc

    def respectful_request(self, url: str, **kwargs) -> requests.Response:
        self.rate_limiter.wait()
        proxies = kwargs.pop("proxies", None) or self.proxy_manager.as_requests()
        if proxies:
            kwargs["proxies"] = proxies
        # Shops whose search form posts (Saxquest) pass `data=`.
        send = self.session.post if "data" in kwargs else self.session.get
        resp = send(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        _fix_encoding(resp)
        return resp

    def finalize(self, records: list[dict]) -> list[dict]:
        """Validate + normalize a batch of raw records."""
        out = []
        for rec in records:
            if not is_valid(rec):
                continue
            out.append(normalize(rec, self.currency))
        return out

    def handle_anti_scrape(self) -> None:
        """Hook for Cloudflare/JS/captcha handling. Override per site."""
        return None

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
