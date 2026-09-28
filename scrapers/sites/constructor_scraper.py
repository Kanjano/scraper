"""Scraper for shops whose search runs on Constructor.io (Andertons).

Like Algolia: the storefront's search box calls Constructor's public search
endpoint with a client key shipped in the page, so the same structured results
are available without rendering the shop.

Config (``constructor`` in the store override): ``key`` (the public client key),
``fields`` (dotted paths inside each result's ``data``: price, sale_price,
url, image, brand).
"""
from urllib.parse import quote, urljoin

from scrapers.base_scraper import BaseScraper
from scrapers.sites.algolia_scraper import _dig

API = "https://ac.cnstrc.com/search/{query}"


class ConstructorScraper(BaseScraper):
    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        cfg = self.config["constructor"]
        fields = cfg["fields"]
        url = API.format(query=quote(query))
        try:
            resp = self.retry_with_backoff(
                self.respectful_request, url,
                params={"key": cfg["key"], "c": "ciojs-client-2.91.0",
                        "num_results_per_page": min(limit, 100)},
            )
            results = resp.json().get("response", {}).get("results", [])
        except Exception as exc:  # noqa: BLE001
            self.logger.error("constructor search failed: %s", exc)
            return []

        records = []
        for item in results[:limit]:
            data = item.get("data") or {}
            price = self.parse_price(_dig(data, fields["price"]))
            sale = self.parse_price(_dig(data, fields.get("sale_price")))
            on_sale = bool(sale and price and sale < price)
            link = _dig(data, fields["url"])
            records.append(
                {
                    "name": item.get("value"),
                    "brand": _dig(data, fields.get("brand")),
                    "price": sale if on_sale else price,
                    "original_price": price if on_sale else None,
                    "currency": self.currency,
                    "url": urljoin(self.config["url"] + "/", link) if link else None,
                    "image": _dig(data, fields.get("image")),
                    "external_id": str(data.get("id") or "") or None,
                    "rating": None,
                    "stock": None,
                }
            )
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        return {"url": product_url}
