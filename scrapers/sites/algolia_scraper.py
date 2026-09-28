"""Scraper for shops whose search runs on Algolia (Sweetwater, Perfect Circuit).

The shop's own search box queries Algolia with a public, search-only key that
ships in the storefront. Asking Algolia directly returns the same structured
hits without touching the shop's bot-protected pages.

Config (``algolia`` in the store override):
    app_id, index            Algolia application and index
    api_key                  static search key, or
    api_key_re               regex (one group) that reads a rotating key from
                             the shop's homepage
    fields                   dotted paths in a hit: name, price, url, brand, stock,
                             image, original_price (list price before a discount)
"""
import re
from urllib.parse import urljoin

from scrapers.base_scraper import BaseScraper


def _dig(obj, path: str | None):
    for key in (path or "").split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


class AlgoliaScraper(BaseScraper):
    def _api_key(self, algolia: dict) -> str:
        if algolia.get("api_key"):
            return algolia["api_key"]
        home = self.respectful_request(self.config["url"])
        return re.search(algolia["api_key_re"], home.text).group(1)

    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        algolia = self.config["algolia"]
        fields = algolia["fields"]
        try:
            app = algolia["app_id"]
            self.rate_limiter.wait()
            resp = self.session.post(
                f"https://{app.lower()}-dsn.algolia.net/1/indexes/{algolia['index']}/query",
                headers={
                    "X-Algolia-Application-Id": app,
                    "X-Algolia-API-Key": self._api_key(algolia),
                },
                json={"query": query, "hitsPerPage": limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as exc:  # noqa: BLE001
            self.logger.error("algolia search failed: %s", exc)
            return []

        records = []
        for hit in hits[:limit]:
            url = _dig(hit, fields["url"])
            records.append(
                {
                    "name": _dig(hit, fields["name"]),
                    "brand": _dig(hit, fields.get("brand")),
                    "price": self.parse_price(_dig(hit, fields["price"])),
                    "currency": self.currency,
                    "url": urljoin(self.config["url"] + "/", url) if url else None,
                    "external_id": str(hit.get("objectID")),
                    "rating": None,
                    "stock": _dig(hit, fields.get("stock")),
                    "original_price": self.parse_price(_dig(hit, fields.get("original_price"))),
                    "image": _dig(hit, fields.get("image")),
                }
            )
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        return {"url": product_url}
