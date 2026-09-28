"""Scraper for shops whose search is served by Doofinder (Gear4music).

The shop's search page sits behind Cloudflare and only paints a Doofinder
overlay; the overlay itself queries Doofinder's public search API with the
store's search-engine hashid. We ask that API directly.

Config (``doofinder`` in the store override): ``hashid`` (the search engine for
the store's language/currency, from ``eu1-config.doofinder.com/2.x/<install>.js``)
and ``zone`` (default ``eu1``).
"""
from urllib.parse import quote_plus, urljoin

from scrapers.base_scraper import BaseScraper


class DoofinderScraper(BaseScraper):
    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        df = self.config["doofinder"]
        url = (
            f"https://{df.get('zone', 'eu1')}-search.doofinder.com/6/{df['hashid']}"
            f"/_search?query={quote_plus(query)}&rpp={min(limit, 100)}"
        )
        try:
            resp = self.retry_with_backoff(
                self.respectful_request, url, headers={"Origin": self.config["url"]}
            )
            results = resp.json().get("results", [])
        except Exception as exc:  # noqa: BLE001
            self.logger.error("doofinder search failed: %s", exc)
            return []

        records = [
            {
                "name": r.get("title"),
                "brand": r.get("brand"),
                "price": r.get("best_price") or r.get("price"),
                # "price" is the list price; "best_price" the current one when on sale.
                "original_price": r.get("price") if (r.get("best_price") or 0) < (r.get("price") or 0) else None,
                "image": r.get("image_link"),
                "currency": self.currency,
                "url": urljoin(self.config["url"] + "/", r["link"]) if r.get("link") else None,
                "external_id": r.get("id"),
                "rating": None,
                "stock": r.get("availability"),
                "condition": r.get("condition"),
            }
            for r in results[:limit]
        ]
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        return {"url": product_url}
