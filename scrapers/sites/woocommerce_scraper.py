"""WooCommerce scraper via the public Store API (``/wp-json/wc/store/v1``).

The Store API is the read-only, unauthenticated API WooCommerce blocks use for
the storefront itself: structured products, prices in minor units, permalinks.
Preferred over parsing theme markup, which differs on every shop.
"""
from html import unescape
from urllib.parse import quote_plus

from scrapers.base_scraper import BaseScraper


def _money(prices, key: str = "price") -> float | None:
    """Store API returns integer minor units + the exponent to apply."""
    if not isinstance(prices, dict):
        return None
    raw = prices.get(key)
    if raw in (None, ""):
        return None
    try:
        minor = int(prices.get("currency_minor_unit", 2))
        return round(int(raw) / (10 ** minor), 2)
    except (TypeError, ValueError):
        return None


class WooCommerceScraper(BaseScraper):
    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        url = self.config["search_url"].format(query=quote_plus(query))
        try:
            resp = self.retry_with_backoff(self.respectful_request, url)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("woocommerce search failed: %s", exc)
            return []
        if not isinstance(data, list):
            return []

        records: list[dict] = []
        for p in data[:limit]:
            if not isinstance(p, dict):
                continue
            prices = p.get("prices") or {}
            # Some shops return category ids instead of objects.
            cats = [c for c in (p.get("categories") or []) if isinstance(c, dict)]
            records.append(
                {
                    "name": unescape(p.get("name") or ""),  # Store API sends "&#038;"
                    "brand": None,
                    "category": cats[0].get("name") if cats else None,
                    "price": _money(prices),
                    "currency": (
                        prices.get("currency_code") if isinstance(prices, dict) else None
                    ) or self.currency,
                    "url": p.get("permalink"),
                    "external_id": str(p.get("id")) if p.get("id") else None,
                    "rating": self.parse_price(str(p.get("average_rating") or "")) or None,
                    "reviews": p.get("review_count") or 0,
                    "stock": 1 if p.get("is_in_stock") else 0,
                    "original_price": _money(prices, "regular_price"),
                    "image": next((i.get("src") for i in p.get("images") or []
                                   if isinstance(i, dict)), None),
                }
            )
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        return {"url": product_url}
