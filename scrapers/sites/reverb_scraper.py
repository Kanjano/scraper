"""Reverb scraper via the official public API (no HTML scraping, no bot bypass).

api.reverb.com serves public listing search anonymously; an optional personal
token (REVERB_API_KEY) raises rate limits. Docs: https://www.reverb-api.com/
Verified live 2026-06.
"""
from urllib.parse import quote_plus

from config.settings import settings
from scrapers.base_scraper import BaseScraper

API_BASE = "https://api.reverb.com/api"


class ReverbScraper(BaseScraper):
    def __init__(self, site_config: dict):
        super().__init__(site_config)
        self.session.headers.update(
            {
                "Accept": "application/hal+json",
                "Accept-Version": "3.0",
                "Content-Type": "application/hal+json",
            }
        )
        if settings.reverb_api_key:
            self.session.headers["Authorization"] = f"Bearer {settings.reverb_api_key}"

    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        url = f"{API_BASE}/listings?query={quote_plus(query)}&per_page={min(limit, 50)}"
        try:
            resp = self.retry_with_backoff(self.respectful_request, url)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("reverb api failed: %s", exc)
            return []

        records: list[dict] = []
        for listing in data.get("listings", [])[:limit]:
            price = listing.get("price") or {}
            web = ((listing.get("_links") or {}).get("web") or {}).get("href")
            photo = ((listing.get("photos") or [{}])[0].get("_links") or {})
            image = next((photo[k]["href"] for k in ("small_crop", "large_crop", "full")
                          if isinstance(photo.get(k), dict)), None)
            records.append(
                {
                    "name": listing.get("title"),
                    "brand": listing.get("make"),
                    "category": (listing.get("categories") or [{}])[0].get("full_name"),
                    "price": self.parse_price(str(price.get("amount", ""))),
                    "currency": price.get("currency", self.currency),
                    "external_id": str(listing.get("id")) if listing.get("id") else None,
                    "url": web,
                    "rating": None,
                    "stock": listing.get("inventory"),
                    "condition": (listing.get("condition") or {}).get("display_name"),
                    "original_price": self.parse_price(
                        str((listing.get("original_price") or {}).get("amount", ""))) or None,
                    "image": image,
                }
            )
        return self.finalize(records)

    def get_product_details(self, product_url: str) -> dict:
        # Public web URL — the API listing already carries full detail.
        return {"url": product_url}
