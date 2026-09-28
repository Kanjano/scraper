"""Shopify storefront scraper via the public catalogue feed.

``/search`` is Disallow-ed in Shopify's default robots.txt (so the handy
``/search/suggest.json`` endpoint is off limits for an automated agent), but
``/products.json`` — the public catalogue feed Shopify itself publishes — is
allowed and far richer: every product with vendor, type, variants and prices.

We fetch the feed once per site (TTL-cached), then filter locally by query
tokens. That is one request per site per refresh instead of one per search, and
no theme/CSS coupling at all.

Large catalogues exceed the feed window (MAX_PAGES x PAGE_SIZE). For those the
shop's collections fill the gap: ``/collections.json`` lists every collection
once, and when the query names one ("fender", "fender custom shop") its own
feed ``/collections/<handle>/products.json`` is read too — the brand's full
range, without walking a catalogue of tens of thousands of products.
"""
import re
from urllib.parse import quote, urlsplit

from cache.cache_manager import cache
from scrapers.base_scraper import BaseScraper

MAX_PAGES = 4  # 4 x 250 = up to 1000 products per shop (and per collection)
PAGE_SIZE = 250
MAX_COLLECTION_PAGES = 8  # collections.json pages: up to 2000 collections
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")


class ShopifyScraper(BaseScraper):
    def _origin(self) -> str:
        split = urlsplit(self.config["search_url"] or self.config["url"])
        return f"{split.scheme}://{split.netloc}"

    def _presentment_currency(self) -> str:
        """The currency this shop actually quotes to us.

        Shopify Markets converts prices per visitor region, so a Japanese or US
        shop can serve EUR here — and `/products.json` never says which currency
        it used. `/cart.js` reports the currency of the current session, which is
        exactly the one those prices are in.
        """
        key = f"shopify:{self.config['id']}:currency"
        cached = cache.get(key)
        if cached:
            return cached
        currency = self.currency
        try:
            resp = self.retry_with_backoff(self.respectful_request, f"{self._origin()}/cart.js")
            found = resp.json().get("currency")
            if isinstance(found, str) and len(found) == 3:
                currency = found.upper()
        except Exception as exc:  # noqa: BLE001 — fall back to the configured one
            self.logger.warning("could not read presentment currency: %s", exc)
        cache.set(key, currency)
        return currency

    def _pages(self, feed: str, key: str, field: str, max_pages: int) -> list[dict]:
        """All items of a paginated Shopify JSON feed (TTL-cached)."""
        cached = cache.get(key)
        if cached is not None:
            return cached
        items: list[dict] = []
        for page in range(1, max_pages + 1):
            url = f"{feed}&page={page}" if "?" in feed else f"{feed}?page={page}"
            try:
                resp = self.retry_with_backoff(self.respectful_request, url)
                batch = resp.json().get(field, [])
            except Exception as exc:  # noqa: BLE001
                self.logger.error("shopify %s page %d failed: %s", field, page, exc)
                break
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        cache.set(key, items)
        return items

    def _catalog(self) -> list[dict]:
        feed = self.config["search_url"] or f"{self._origin()}/products.json?limit={PAGE_SIZE}"
        return self._pages(feed, f"shopify:{self.config['id']}:catalog", "products", MAX_PAGES)

    def _collection_handles(self) -> set[str]:
        items = self._pages(
            f"{self._origin()}/collections.json?limit={PAGE_SIZE}",
            f"shopify:{self.config['id']}:collections", "collections", MAX_COLLECTION_PAGES,
        )
        return {c["handle"] for c in items if isinstance(c, dict) and c.get("handle")}

    def _collection_products(self, query: str) -> list[dict]:
        """Products of the collections the query names (longest name first).

        "fender custom shop" tries fender-custom-shop, fender-custom,
        custom-shop, fender, … and reads at most two existing collections.
        """
        words = [w for w in _slug(query).split("-") if w]
        wanted = [
            "-".join(words[i:i + n])
            for n in range(len(words), 0, -1)
            for i in range(len(words) - n + 1)
        ]
        handles = self._collection_handles()
        picked = [h for h in wanted if h in handles][:2]
        products: list[dict] = []
        for handle in picked:
            products += self._pages(
                f"{self._origin()}/collections/{quote(handle)}/products.json?limit={PAGE_SIZE}",
                f"shopify:{self.config['id']}:collection:{handle}", "products", MAX_PAGES,
            )
        return products

    @staticmethod
    def _matches(product: dict, tokens: list[str]) -> bool:
        haystack = " ".join(
            str(product.get(f) or "")
            for f in ("title", "vendor", "product_type", "handle", "tags")
        ).lower()
        return all(t in haystack for t in tokens)

    def _record(self, p: dict, currency: str | None = None) -> dict:
        variants = [v for v in (p.get("variants") or []) if v.get("price") is not None]
        priced = [(self.parse_price(str(v["price"])), v) for v in variants]
        priced = [(pr, v) for pr, v in priced if pr]
        prices = [pr for pr, _ in priced]
        # compare_at_price of the cheapest variant = its price before the discount.
        cheapest = min(priced, key=lambda x: x[0])[1] if priced else {}
        was = self.parse_price(str(cheapest.get("compare_at_price") or "")) or None
        images = p.get("images") or []
        handle = p.get("handle")
        return {
            "name": p.get("title"),
            "brand": p.get("vendor") or None,
            "category": p.get("product_type") or None,
            "price": min(prices) if prices else None,
            "currency": currency or self.currency,
            "url": f"{self._origin()}/products/{quote(handle)}" if handle else None,
            "external_id": str(p.get("id")) if p.get("id") else handle,
            "rating": None,
            "stock": 1 if any(v.get("available") for v in (p.get("variants") or [])) else 0,
            "original_price": was,
            "image": images[0].get("src") if images and isinstance(images[0], dict) else None,
        }

    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        tokens = [t for t in query.lower().split() if t]
        products = self._catalog()
        if len(products) >= MAX_PAGES * PAGE_SIZE:  # the feed window is full: catalogue is bigger
            seen = {p.get("id") for p in products}
            products = products + [p for p in self._collection_products(query)
                                   if p.get("id") not in seen]
        matches = [p for p in products if self._matches(p, tokens)]
        if not matches:
            return []
        currency = self._presentment_currency()
        return self.finalize([self._record(p, currency) for p in matches[:limit]])

    def get_product_details(self, product_url: str) -> dict:
        """Shopify serves per-product JSON at ``<product-url>.js``."""
        url = product_url.split("?")[0].rstrip("/") + ".js"
        try:
            resp = self.retry_with_backoff(self.respectful_request, url)
            p = resp.json()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("shopify details failed: %s", exc)
            return {}
        rec = self._record(p, self._presentment_currency())
        rec["url"] = product_url
        return rec
