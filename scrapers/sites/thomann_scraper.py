"""Thomann scraper.

Thomann renders product *prices* via JS into empty spans, but ships a full
GA4 ecommerce payload (`ecommerceEventItem`) for every product in the static
HTML — item_id, item_name, item_brand, item_category, price, currency. We parse
that JSON (robust, no Selenium) and pair it with the product anchor hrefs from
the DOM (same document order) to recover product URLs.

Verified live 2026-06 against https://www.thomann.de/intl/search_dir.html?sw=
"""
import json
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scrapers.sites.generic_scraper import GenericScraper

_ITEM_RE = re.compile(r'"ecommerceEventItem":(\{.*?\})')


class ThomannScraper(GenericScraper):
    def search(self, query: str, limit: int = 20, **kwargs) -> list[dict]:
        url = self.config["search_url"].format(query=quote_plus(query))
        try:
            resp = self.retry_with_backoff(self.respectful_request, url)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("search failed: %s", exc)
            return []

        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # Product URLs in document order (aligns with the JSON item order).
        hrefs = [
            a.get("href")
            for a in soup.select("div.fx-product-list-entry a.product__content")
        ]

        # Product photos, keyed by the same product id the GA4 items carry.
        images = {}
        for card in soup.select("div.fx-product-list-entry[data-product-id]"):
            src = next((s.get("data-srcset") for s in card.select("source[data-srcset]")
                        if (s.get("data-srcset") or "").split()[0].endswith(".jpg")), None)
            if src:
                images[card["data-product-id"]] = src.split()[0]

        records: list[dict] = []
        seen: set[str] = set()
        for idx, raw in enumerate(_ITEM_RE.findall(html)):
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            item_id = str(d.get("item_id") or "")
            if item_id in seen:
                continue
            seen.add(item_id)
            href = hrefs[idx] if idx < len(hrefs) else None
            records.append(
                {
                    "name": d.get("item_name"),
                    "brand": d.get("item_brand"),
                    "category": d.get("item_category"),
                    "price": d.get("price"),
                    "currency": d.get("currency", self.currency),
                    "external_id": item_id or None,
                    "url": urljoin(self.config["url"], href) if href else None,
                    "rating": None,
                    "image": images.get(item_id),
                }
            )
            if len(records) >= limit:
                break

        return self.finalize(records)
